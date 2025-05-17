import os
import sys
import tempfile
import subprocess
import shutil
from moviepy.editor import VideoFileClip
import numpy as np
import soundfile as sf
import uuid
import logging

logger = logging.getLogger("derusher")

class DerushWorker:
    def __init__(self, video_path, min_silence_len=400, silence_thresh=-45, max_thresh=-10, margin_ms=600):
        self.video_path = video_path
        self.min_silence_len = min_silence_len / 1000.0  # Conversion en secondes
        self.silence_thresh = silence_thresh
        self.max_thresh = max_thresh
        self.margin = margin_ms / 1000.0  # Conversion en secondes
        self.min_segment_gap = 0.2  # 200ms minimum entre segments
        self.temp_dir = None
        self.progress_callback = None

    def set_progress_callback(self, callback):
        """Permet de définir une fonction de rappel pour mettre à jour la progression"""
        self.progress_callback = callback

    def update_progress(self, value):
        """Met à jour la progression si un callback est défini"""
        if self.progress_callback:
            self.progress_callback(value)

    def create_temp_directory(self):
        """Crée un répertoire temporaire pour les segments"""
        self.temp_dir = tempfile.mkdtemp(prefix='derusher_')
        return self.temp_dir

    def cleanup_temp_directory(self):
        """Nettoie le répertoire temporaire"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            for file in os.listdir(self.temp_dir):
                try:
                    os.remove(os.path.join(self.temp_dir, file))
                except:
                    logger.warning(f"Impossible de supprimer {os.path.join(self.temp_dir, file)}")
            try:
                os.rmdir(self.temp_dir)
            except:
                logger.warning(f"Impossible de supprimer le répertoire temporaire {self.temp_dir}")

    def merge_overlapping_ranges(self, ranges):
        """Fusionne les segments qui se chevauchent ou sont très proches"""
        if not ranges:
            return []
        
        # Trier les segments par temps de début
        sorted_ranges = sorted(ranges, key=lambda x: x[0])
        merged = []
        current_start, current_end = sorted_ranges[0]
        
        for start, end in sorted_ranges[1:]:
            # Si le début du segment actuel est très proche ou chevauche la fin du segment précédent
            if start <= current_end + self.min_segment_gap:
                # Étendre le segment actuel
                current_end = max(current_end, end)
            else:
                # Ajouter le segment précédent et commencer un nouveau
                merged.append((current_start, current_end))
                current_start, current_end = start, end
        
        # Ajouter le dernier segment
        merged.append((current_start, current_end))
        return merged

    def detect_nonsilent(self, audio_array, sample_rate):
        """Détecte les segments non silencieux dans un array audio"""
        # Calculer la RMS (Root Mean Square) par fenêtre
        window_size = int(0.1 * sample_rate)  # fenêtre de 100ms
        windows = np.array_split(audio_array, len(audio_array) // window_size)
        
        # Calculer le RMS pour chaque fenêtre
        rms = [np.sqrt(np.mean(window**2)) for window in windows]
        
        # Convertir les seuils de dB en amplitude linéaire
        min_threshold = 10 ** (self.silence_thresh / 20)
        max_threshold = 10 ** (self.max_thresh / 20)
        
        # Trouver les fenêtres avec un niveau sonore acceptable
        valid_windows = [i for i, r in enumerate(rms) if min_threshold < r < max_threshold]
        
        if not valid_windows:
            return []
        
        # Grouper les fenêtres consécutives
        ranges = []
        start_i = valid_windows[0]
        prev_i = start_i
        
        for i in valid_windows[1:]:
            if i - prev_i > 1:  # Gap trouvé
                end_i = prev_i
                # Convertir les indices de fenêtres en secondes
                start_time = max(0, (start_i * 0.1) - self.margin)  # Ajouter la marge au début
                end_time = (end_i + 1) * 0.1 + self.margin  # Ajouter la marge à la fin
                if end_time - start_time >= self.min_silence_len:
                    ranges.append((start_time, end_time))
                start_i = i
            prev_i = i
        
        # Ajouter le dernier segment
        end_time = min((prev_i + 1) * 0.1 + self.margin, len(audio_array) / sample_rate)
        start_time = max(0, start_i * 0.1 - self.margin)
        if end_time - start_time >= self.min_silence_len:
            ranges.append((start_time, end_time))
        
        # Fusionner les segments qui se chevauchent
        return self.merge_overlapping_ranges(ranges)

    def extract_segment_ffmpeg(self, input_file, output_file, start_time, end_time):
        """Extrait un segment vidéo avec FFmpeg pour maintenir la synchronisation"""
        cmd = [
            'ffmpeg', '-y',
            '-i', input_file,
            '-ss', f"{start_time:.3f}",
            '-t', f"{end_time - start_time:.3f}",
            '-c:v', 'libx264', '-preset', 'fast',
            '-c:a', 'aac',
            '-avoid_negative_ts', '1',
            output_file
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur FFmpeg: {e}")
            return False
        except FileNotFoundError:
            logger.error("FFmpeg introuvable dans le PATH")
            return False

    def concat_segments_ffmpeg(self, segment_files, output_file):
        """Concatène les segments avec FFmpeg"""
        if not segment_files:
            raise ValueError("Aucun segment à concaténer")
        
        # Vérifier que tous les fichiers existent
        missing_files = [f for f in segment_files if not os.path.exists(f)]
        if missing_files:
            raise FileNotFoundError(f"Fichiers segments manquants: {missing_files[:5]}...")
        
        # Créer un fichier de liste pour FFmpeg
        list_file = os.path.join(self.temp_dir, 'segments.txt')
        with open(list_file, 'w') as f:
            for segment in segment_files:
                f.write(f"file '{segment}'\n")

        # Concaténer les segments
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            output_file
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur FFmpeg lors de la concaténation: {e}")
            return False
        except FileNotFoundError:
            logger.error("FFmpeg introuvable dans le PATH")
            return False

    def run(self):
        """Exécute le processus de dérushage complet"""
        temp_audio_path = None
        
        try:
            logger.info("Création du répertoire temporaire...")
            temp_dir = self.create_temp_directory()
            self.update_progress(5)
            
            logger.info("Chargement de la vidéo...")
            video = VideoFileClip(self.video_path)
            self.update_progress(10)
            
            logger.info("Extraction de l'audio...")
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio_path = temp_audio.name
            temp_audio.close()
            
            # Extraire l'audio sans mode verbose
            video.audio.write_audiofile(temp_audio_path, codec='pcm_s16le', verbose=False, logger=None)
            self.update_progress(25)
            
            logger.info("Analyse des segments audio...")
            audio_data, sample_rate = sf.read(temp_audio_path)
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)  # Convertir en mono si stéréo
            
            nonsilent_ranges = self.detect_nonsilent(audio_data, sample_rate)
            
            if not nonsilent_ranges:
                raise ValueError("Aucun segment audio détecté avec ces paramètres")
            
            logger.info(f"{len(nonsilent_ranges)} segments détectés")
            
            # Fermer la vidéo pour libérer les ressources
            video.close()
            self.update_progress(30)
            
            logger.info("Extraction des segments vidéo...")
            segment_files = []
            for i, (start, end) in enumerate(nonsilent_ranges):
                # S'assurer que les timestamps sont dans les limites
                start = max(0, start)
                end = min(end, video.duration)
                
                # Nom du fichier de segment
                segment_file = os.path.join(temp_dir, f'segment_{i:04d}.mp4')
                segment_files.append(segment_file)
                
                # Extraire le segment
                logger.info(f"Traitement segment {i+1}/{len(nonsilent_ranges)} ({start:.2f}s - {end:.2f}s)")
                success = self.extract_segment_ffmpeg(self.video_path, segment_file, start, end)
                
                if not success:
                    raise RuntimeError("Échec de l'extraction du segment vidéo avec FFmpeg")
                
                # Mise à jour de la progression
                progress = 30 + ((i + 1) / len(nonsilent_ranges)) * 50
                self.update_progress(int(progress))
            
            logger.info("Concaténation des segments...")
            output_path = os.path.splitext(self.video_path)[0] + '_derushed.mp4'
            success = self.concat_segments_ffmpeg(segment_files, output_path)
            
            if not success:
                raise RuntimeError("Échec de la concaténation des segments avec FFmpeg")
            
            self.update_progress(95)
            
            # Nettoyage
            logger.info("Nettoyage des fichiers temporaires...")
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                except:
                    logger.warning(f"Impossible de supprimer {temp_audio_path}")
            self.cleanup_temp_directory()
            
            self.update_progress(100)
            logger.info(f"Vidéo dérushée sauvegardée: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Échec du dérushage: {str(e)}")
            # Nettoyage même en cas d'erreur
            try:
                if temp_audio_path and os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
                self.cleanup_temp_directory()
            except Exception as cleanup_error:
                logger.warning(f"Erreur supplémentaire pendant le nettoyage: {cleanup_error}")
            raise e

def check_ffmpeg_installed():
    """Vérifie si FFmpeg est disponible dans le PATH du système"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE, 
                              text=True, 
                              check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def process_video(video_path, min_silence_len=400, silence_thresh=-45, max_thresh=-10, margin_ms=600, progress_callback=None):
    """
    Dérushe une vidéo (supprime les silences)
    
    Parameters:
    - video_path: Chemin de la vidéo d'entrée
    - min_silence_len: Longueur minimale d'un segment en ms
    - silence_thresh: Seuil de silence en dB
    - max_thresh: Seuil maximum en dB
    - margin_ms: Marge avant/après les segments en ms
    - progress_callback: Fonction de rappel pour la progression
    
    Returns:
    - Chemin de la vidéo dérushée
    """
    # Vérifier que FFmpeg est installé
    if not check_ffmpeg_installed():
        raise RuntimeError("FFmpeg n'est pas installé ou n'est pas dans le PATH du système.")
    
    # Créer le worker et définir le callback de progression
    worker = DerushWorker(
        video_path,
        min_silence_len,
        silence_thresh,
        max_thresh,
        margin_ms
    )
    
    if progress_callback:
        worker.set_progress_callback(progress_callback)
    
    # Exécuter le dérushage
    return worker.run() 