import os
import re
import subprocess
import uuid
import tempfile
import shutil
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor
import requests
import m3u8
from app.utils.file_handler import write_concat_list

# Default configurations
DEFAULT_COOKIE = ""
DEFAULT_VARIANT_BANDWIDTH = 3200000  # 1080p
MAX_CONCURRENT_DOWNLOADS = 5

# Thread pool for concurrent downloads
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS)

def get_headers(cookie=""):
    """Génère les headers HTTP standard pour les requêtes."""
    headers = {
        "Referer": "https://www.loom.com/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        )
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers

def find_master_url(share_url, cookie=""):
    """Télécharge la page de partage et extrait l'URL master playlist HLS."""
    headers = get_headers(cookie)
    r = requests.get(share_url, headers=headers)
    r.raise_for_status()
    html = r.text
    # On cherche le fragment HLS dans le <script> ou la config JSON de la page
    m = re.search(r'(https://[^"]+?/resource/hls/playlist\.m3u8\?[^"]+)', html)
    if not m:
        raise RuntimeError("Impossible de trouver l'URL HLS dans la page.")
    return m.group(1)

def fetch_master(master_url, cookie=""):
    """Récupère et parse le master playlist, renvoie (m3u8_obj, base_url, query)."""
    headers = get_headers(cookie)
    r = requests.get(master_url, headers=headers)
    r.raise_for_status()
    master = m3u8.loads(r.text)
    base = master_url.split("playlist.m3u8",1)[0]
    query = urlsplit(master_url).query
    return master, base, query

def download_segment(seg_url, query, local_path, cookie=""):
    """Télécharge un segment individuel."""
    headers = get_headers(cookie)
    signed = f"{seg_url}?{query}"
    
    # Skip if file already exists
    if os.path.exists(local_path):
        return local_path
        
    rr = requests.get(signed, headers=headers, stream=True)
    rr.raise_for_status()
    with open(local_path, "wb") as f:
        for chunk in rr.iter_content(8192):
            f.write(chunk)
    return local_path

def download_playlist(uri, base, query, folder, cookie=""):
    """Télécharge tous les segments TS d'une URI (audio ou vidéo) de façon concurrente."""
    headers = get_headers(cookie)
    os.makedirs(folder, exist_ok=True)
    
    url = uri if uri.startswith("http") else base + uri
    r = requests.get(f"{url}?{query}", headers=headers)
    r.raise_for_status()
    playlist = m3u8.loads(r.text)
    
    # Prepare download tasks
    download_tasks = []
    local_files = []
    
    for seg in playlist.segments:
        seg_url = seg.uri if seg.uri.startswith("http") else base + seg.uri
        local = os.path.join(folder, os.path.basename(seg.uri))
        local_files.append(local)
        
        # Add to download tasks if file doesn't exist
        if not os.path.exists(local):
            download_tasks.append((seg_url, query, local, cookie))
    
    # Use map for simpler concurrency
    if download_tasks:
        list(executor.map(
            lambda args: download_segment(*args),
            download_tasks
        ))
    
    return local_files

def download_loom_video(share_url, output_file, cookie=DEFAULT_COOKIE, variant_bandwidth=DEFAULT_VARIANT_BANDWIDTH):
    """
    Télécharge une vidéo Loom à partir de son URL de partage.
    
    Parameters:
    - share_url: L'URL de partage Loom
    - output_file: Le nom du fichier de sortie
    - cookie: Cookie Loom pour les liens non-publics (optionnel)
    - variant_bandwidth: Qualité en bits/s (1500000 pour 720p, 3200000 pour 1080p)
    
    Returns:
    - Le chemin vers le fichier téléchargé
    """
    session_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix=f"loom_{session_id}_")
    video_dir = os.path.join(temp_dir, "video")
    audio_dir = os.path.join(temp_dir, "audio")
    
    try:
        # Extraction de l'URL master HLS
        master_url = find_master_url(share_url, cookie)
        
        # Récupération du master playlist
        master, base, query = fetch_master(master_url, cookie)
        
        # Téléchargement vidéo
        try:
            vid_uri = next(pl.uri for pl in master.playlists 
                        if pl.stream_info.bandwidth == variant_bandwidth)
        except StopIteration:
            # Si la qualité demandée n'est pas disponible, prendre la plus haute qualité
            highest_bandwidth = 0
            for pl in master.playlists:
                if pl.stream_info.bandwidth > highest_bandwidth:
                    highest_bandwidth = pl.stream_info.bandwidth
                    vid_uri = pl.uri
            if highest_bandwidth == 0:
                raise RuntimeError("Aucune piste vidéo trouvée dans le master playlist.")
        
        video_files = download_playlist(vid_uri, base, query, video_dir, cookie)
        video_list = os.path.join(temp_dir, "video.txt")
        write_concat_list(video_files, video_list)
        
        # Téléchargement audio
        try:
            audio_uri = next(m for m in master.media if m.type=="AUDIO" and m.default).uri
        except StopIteration:
            # Fallback si aucun audio par défaut n'est spécifié
            try:
                audio_uri = next(m for m in master.media if m.type=="AUDIO").uri
            except StopIteration:
                raise RuntimeError("Aucune piste audio trouvée dans le master playlist.")
                
        audio_files = download_playlist(audio_uri, base, query, audio_dir, cookie)
        audio_list = os.path.join(temp_dir, "audio.txt")
        write_concat_list(audio_files, audio_list)
        
        # Fichiers temporaires pour concaténation
        temp_video = os.path.join(temp_dir, f"temp_video_{session_id}.mp4")
        temp_audio = os.path.join(temp_dir, f"temp_audio_{session_id}.mp4")
        
        # Concaténation vidéo
        subprocess.run([
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", video_list, "-c", "copy", temp_video
        ], check=True)
        
        # Concaténation audio
        subprocess.run([
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", audio_list, "-c", "copy", temp_audio
        ], check=True)
        
        # Muxage final
        subprocess.run([
            "ffmpeg", "-i", temp_video, "-i", temp_audio,
            "-c", "copy", output_file
        ], check=True)
        
        return output_file
        
    finally:
        # Nettoyage des fichiers temporaires
        try:
            shutil.rmtree(temp_dir)
        except:
            pass 