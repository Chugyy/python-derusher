#!/usr/bin/env python3
import os
import sys
import time
import uuid
import argparse
import tempfile
import requests
import logging
from pathlib import Path
from app.derusher import process_video, check_ffmpeg_installed

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("derusher-cli")

# Création du dossier temp pour les fichiers temporaires
os.makedirs("temp", exist_ok=True)

def print_progress(progress):
    """Affiche la progression du dérushage en pourcentage"""
    print(f"Progression: {progress}%", end="\r")
    sys.stdout.flush()

def list_temp_videos():
    """Liste les fichiers vidéo MP4 dans le dossier temp"""
    try:
        temp_files = [f for f in os.listdir("temp") if f.endswith('.mp4') and not f.endswith('_derushed.mp4')]
        if not temp_files:
            return []
        return temp_files
    except FileNotFoundError:
        os.makedirs("temp", exist_ok=True)
        return []

def download_from_local_server(url, output_path):
    """Télécharge une vidéo en utilisant le serveur local à l'URL http://localhost:8000/download"""
    try:
        # Vérifier que le serveur est en cours d'exécution
        try:
            r = requests.get("http://localhost:8000/check", timeout=5)
            if r.status_code != 200:
                print(f"[ERREUR] Le serveur n'est pas en cours d'exécution ou n'est pas accessible (code {r.status_code})")
                return False
        except requests.exceptions.ConnectionError:
            print("[ERREUR] Impossible de se connecter au serveur local. Assurez-vous qu'il est en cours d'exécution avec 'python server.py'")
            return False
        
        # Construire l'URL avec les paramètres
        download_url = f"http://localhost:8000/download?url={url}&output={output_path}"
        
        print(f"[INFO] Téléchargement de la vidéo avec le serveur local...")
        print(f"[INFO] URL de la vidéo: {url}")
        print(f"[INFO] Chemin de sortie: {output_path}")
        
        # Effectuer la requête
        response = requests.get(download_url, stream=True, timeout=600)  # Timeout de 10 minutes
        
        if response.status_code == 200:
            # Le serveur sauvegarde directement le fichier à output_path
            # Vérifier si le fichier a été créé
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"[SUCCÈS] Vidéo téléchargée avec succès: {output_path}")
                return True
            else:
                print(f"[ERREUR] Le fichier n'a pas été créé ou est vide: {output_path}")
                return False
        else:
            print(f"[ERREUR] Échec du téléchargement (code {response.status_code}): {response.text}")
            return False
            
    except Exception as e:
        print(f"[ERREUR] Exception lors du téléchargement: {str(e)}")
        return False

def download_and_derush_video(url, derush=True):
    """Télécharge et dérushe une vidéo à partir d'une URL"""
    # Vérifier que FFmpeg est installé
    if not check_ffmpeg_installed():
        print("[ERREUR CRITIQUE] FFmpeg n'est pas installé ou n'est pas accessible.")
        print("Téléchargez et installez FFmpeg depuis https://ffmpeg.org/download.html")
        return None
    
    # Générer un nom de fichier temporaire unique
    temp_id = str(uuid.uuid4())[:8]
    temp_video_path = os.path.abspath(f"temp/video_{temp_id}.mp4")
    
    # Télécharger la vidéo avec le serveur local
    print(f"\n[ÉTAPE 1] Téléchargement de la vidéo depuis: {url}")
    if not download_from_local_server(url, temp_video_path):
        print("[ERREUR] Échec du téléchargement de la vidéo.")
        return None
    
    # Si le dérushage n'est pas demandé, renvoyer le chemin de la vidéo téléchargée
    if not derush:
        print(f"[INFO] Dérushage désactivé. Vidéo téléchargée: {temp_video_path}")
        return temp_video_path
    
    # Dérusher la vidéo téléchargée
    try:
        print("\n[ÉTAPE 2] Dérushage de la vidéo...")
        derushed_path = process_video(
            temp_video_path,
            min_silence_len=1000,
            silence_thresh=-50,
            max_thresh=-10,
            margin_ms=200,
            progress_callback=print_progress
        )
        
        print(f"\n[SUCCÈS] Vidéo dérushée: {derushed_path}")
        
        # Supprimer le fichier original
        try:
            os.remove(temp_video_path)
            print(f"[INFO] Fichier temporaire supprimé: {temp_video_path}")
        except Exception as e:
            print(f"[AVERTISSEMENT] Impossible de supprimer le fichier temporaire: {str(e)}")
        
        return derushed_path
        
    except Exception as e:
        print(f"[ERREUR] Échec du dérushage: {str(e)}")
        return temp_video_path

def derush_existing_video(video_path):
    """Dérushe une vidéo existante"""
    # Vérifier que FFmpeg est installé
    if not check_ffmpeg_installed():
        print("[ERREUR CRITIQUE] FFmpeg n'est pas installé ou n'est pas accessible.")
        print("Téléchargez et installez FFmpeg depuis https://ffmpeg.org/download.html")
        return None
    
    # Vérifier que le fichier existe
    if not os.path.exists(video_path):
        print(f"[ERREUR] Le fichier vidéo n'existe pas: {video_path}")
        return None
    
    # Dérusher la vidéo
    try:
        print(f"\n[ÉTAPE 1] Dérushage de la vidéo: {video_path}")
        derushed_path = process_video(
            video_path,
            min_silence_len=1000,
            silence_thresh=-50,
            max_thresh=-10,
            margin_ms=200,
            progress_callback=print_progress
        )
        
        print(f"\n[SUCCÈS] Vidéo dérushée: {derushed_path}")
        return derushed_path
        
    except Exception as e:
        print(f"[ERREUR] Échec du dérushage: {str(e)}")
        return None

def main():
    """Fonction principale du CLI"""
    parser = argparse.ArgumentParser(description="Dérusher CLI - Téléchargement et dérushage de vidéos")
    
    # Sous-commandes
    subparsers = parser.add_subparsers(dest="command", help="Commande à exécuter")
    
    # Commande 'download'
    download_parser = subparsers.add_parser("download", help="Télécharger une vidéo depuis une URL")
    download_parser.add_argument("url", help="URL de la vidéo à télécharger")
    download_parser.add_argument("--no-derush", action="store_true", help="Désactiver le dérushage")
    
    # Commande 'derush'
    derush_parser = subparsers.add_parser("derush", help="Dérusher une vidéo existante")
    derush_parser.add_argument("path", help="Chemin de la vidéo à dérusher")
    
    # Commande 'list'
    list_parser = subparsers.add_parser("list", help="Lister les vidéos dans le dossier temp")
    
    # Analyser les arguments
    args = parser.parse_args()
    
    # Menu interactif si aucune commande n'est spécifiée
    if args.command is None:
        print("\n===== DERUSHER CLI =====")
        choice = input("Que souhaitez-vous faire?\n1. Télécharger et dérusher une vidéo\n2. Dérusher une vidéo existante\nChoix (1/2): ")
        
        if choice == "1":
            video_url = input("\nEntrez l'URL de la vidéo à télécharger: ")
            if not video_url:
                print("Erreur: Aucune URL fournie.")
                sys.exit(1)
                
            derush_choice = input("Voulez-vous dérusher la vidéo après le téléchargement? (o/n, défaut: o): ").lower()
            derush = derush_choice != "n"
            
            video_path = download_and_derush_video(video_url, derush)
            
            if video_path:
                print(f"\n[PROCESSUS TERMINÉ AVEC SUCCÈS]")
                print(f"La vidéo est disponible ici: {video_path}")
            else:
                print("\n[PROCESSUS TERMINÉ AVEC DES ERREURS]")
            
        elif choice == "2":
            # Lister les vidéos disponibles dans le dossier temp
            temp_videos = list_temp_videos()
            if not temp_videos:
                # Demander le chemin d'une vidéo
                video_path = input("\nAucune vidéo trouvée dans le dossier temp. Entrez le chemin complet d'une vidéo: ")
                if not video_path:
                    print("Erreur: Aucun chemin fourni.")
                    sys.exit(1)
            else:
                print("\nVidéos disponibles dans le dossier 'temp':")
                for i, video in enumerate(temp_videos, 1):
                    print(f"{i}. {video}")
                    
                while True:
                    try:
                        video_choice_str = input("\nChoisissez le numéro de la vidéo à dérusher (ou 'p' pour spécifier un chemin): ")
                        if video_choice_str.lower() == 'p':
                            video_path = input("Entrez le chemin complet de la vidéo: ")
                            if not video_path:
                                print("Erreur: Aucun chemin fourni.")
                                continue
                            break
                            
                        video_choice_idx = int(video_choice_str)
                        if 1 <= video_choice_idx <= len(temp_videos):
                            video_path = os.path.abspath(os.path.join("temp", temp_videos[video_choice_idx-1]))
                            break
                        print("Choix invalide. Veuillez réessayer.")
                    except ValueError:
                        print("Veuillez entrer un nombre valide ou 'p'.")
            
            # Dérusher la vidéo sélectionnée
            derushed_path = derush_existing_video(video_path)
            
            if derushed_path:
                print(f"\n[PROCESSUS TERMINÉ AVEC SUCCÈS]")
                print(f"La vidéo dérushée est disponible ici: {derushed_path}")
            else:
                print("\n[PROCESSUS TERMINÉ AVEC DES ERREURS]")
                
        else:
            print("Choix invalide. Veuillez entrer 1 ou 2.")
            sys.exit(1)
    
    # Exécuter la commande spécifiée
    elif args.command == "download":
        video_path = download_and_derush_video(args.url, not args.no_derush)
        
        if video_path:
            print(f"\n[PROCESSUS TERMINÉ AVEC SUCCÈS]")
            print(f"La vidéo est disponible ici: {video_path}")
        else:
            print("\n[PROCESSUS TERMINÉ AVEC DES ERREURS]")
            sys.exit(1)
            
    elif args.command == "derush":
        derushed_path = derush_existing_video(args.path)
        
        if derushed_path:
            print(f"\n[PROCESSUS TERMINÉ AVEC SUCCÈS]")
            print(f"La vidéo dérushée est disponible ici: {derushed_path}")
        else:
            print("\n[PROCESSUS TERMINÉ AVEC DES ERREURS]")
            sys.exit(1)
            
    elif args.command == "list":
        temp_videos = list_temp_videos()
        if not temp_videos:
            print("Aucune vidéo trouvée dans le dossier temp.")
        else:
            print("\nVidéos disponibles dans le dossier 'temp':")
            for i, video in enumerate(temp_videos, 1):
                print(f"{i}. {video}")

if __name__ == "__main__":
    main() 