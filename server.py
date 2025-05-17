import os
import sys
import time
import uuid
import logging
import tempfile
import uvicorn
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Form, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel, HttpUrl

# Importation des modules personnalisés
from app.loom_downloader import download_loom_video
from app.derusher import process_video, check_ffmpeg_installed
from app.utils.cleanup import cleanup_old_downloads

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("derusher-server")

# Création des répertoires nécessaires
os.makedirs("outputs", exist_ok=True)

# Initialisation de l'application FastAPI
app = FastAPI(
    title="Derusher - API de téléchargement et dérushage de vidéos",
    description="API pour télécharger et dérusher des vidéos Loom",
    version="1.0.0"
)

# Ajout du middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialisation du planificateur pour les tâches périodiques
scheduler = AsyncIOScheduler()

# Modèles de données
class DownloadRequest(BaseModel):
    url: HttpUrl
    cookie: Optional[str] = ""
    quality: Optional[int] = 3200000  # 1080p par défaut
    derush: Optional[bool] = False    # Dérushage activé ou non

class DerushSettings(BaseModel):
    min_silence_len: Optional[int] = 1000
    silence_thresh: Optional[int] = -50
    max_thresh: Optional[int] = -10
    margin_ms: Optional[int] = 200

# Routes
@app.get("/")
def read_root():
    return {"message": "Bienvenue sur l'API Derusher", "status": "online"}

@app.get("/check")
def check_requirements():
    """Vérifie si les prérequis sont installés."""
    ffmpeg_installed = check_ffmpeg_installed()
    return {
        "ffmpeg_installed": ffmpeg_installed,
        "status": "ready" if ffmpeg_installed else "missing_dependencies"
    }

def log_progress(progress):
    """Fonction pour loguer la progression du dérushage"""
    logger.info(f"Progression: {progress}%")

@app.get("/download")
async def download_video(
    url: str = Query(..., description="L'URL de partage Loom à télécharger"),
    cookie: Optional[str] = Query("", description="Cookie Loom optionnel pour les vidéos privées"),
    quality: Optional[int] = Query(3200000, description="Qualité vidéo (1500000 pour 720p, 3200000 pour 1080p)"),
    derush: Optional[bool] = Query(False, description="Activer le dérushage de la vidéo"),
    min_silence_len: Optional[int] = Query(1000, description="Longueur minimale d'un segment en ms"),
    silence_thresh: Optional[int] = Query(-50, description="Seuil de silence en dB"),
    max_thresh: Optional[int] = Query(-10, description="Seuil maximum en dB"),
    margin_ms: Optional[int] = Query(200, description="Marge avant/après les segments en ms"),
    output_path: Optional[str] = Query(None, alias="output", description="Chemin complet de sortie optionnel")
):
    """
    Télécharge une vidéo Loom et optionnellement la dérushe.
    
    - **url**: L'URL de partage Loom
    - **cookie**: Optionnel - Cookie Loom pour les vidéos privées
    - **quality**: Optionnel - Qualité vidéo (1500000 pour 720p, 3200000 pour 1080p)
    - **derush**: Optionnel - Activer le dérushage de la vidéo (suppression des silences)
    - **min_silence_len**: Optionnel - Longueur minimale d'un segment en ms
    - **silence_thresh**: Optionnel - Seuil de silence en dB
    - **max_thresh**: Optionnel - Seuil maximum en dB
    - **margin_ms**: Optionnel - Marge avant/après les segments en ms
    - **output**: Optionnel - Chemin complet où sauvegarder la vidéo
    """
    try:
        # Génération d'un ID unique pour le téléchargement
        download_id = str(uuid.uuid4())
        
        # Définition des chemins de fichiers
        if output_path:
            # L'utilisateur a fourni un chemin de sortie
            final_output_filename = output_path
            final_output_dir = os.path.dirname(final_output_filename)
            if final_output_dir:  # Peut être vide si output_path est juste un nom de fichier
                os.makedirs(final_output_dir, exist_ok=True)
        else:
            # Utilisation d'un nom temporaire dans le dossier outputs
            final_output_filename = f"outputs/loom_{download_id}.mp4"
        
        # Nom de fichier intermédiaire si dérushage demandé
        if derush:
            temp_output_filename = f"outputs/temp_loom_{download_id}.mp4"
        else:
            temp_output_filename = final_output_filename
        
        logger.info(f"Démarrage téléchargement pour URL: {url}")
        start_time = time.time()
        
        # Téléchargement de la vidéo
        download_loom_video(url, temp_output_filename, cookie, quality)
        
        download_time = time.time() - start_time
        logger.info(f"Téléchargement terminé en {download_time:.2f}s")
        
        # Dérushage de la vidéo si demandé
        if derush:
            logger.info(f"Démarrage du dérushage de la vidéo")
            start_derush_time = time.time()
            
            try:
                derushed_output = process_video(
                    temp_output_filename,
                    min_silence_len,
                    silence_thresh,
                    max_thresh,
                    margin_ms,
                    log_progress
                )
                
                # Déplacer le fichier dérushé vers le chemin final si un chemin personnalisé est fourni
                if output_path:
                    import shutil
                    shutil.move(derushed_output, final_output_filename)
                else:
                    final_output_filename = derushed_output
                
                # Supprimer le fichier temporaire
                if os.path.exists(temp_output_filename) and temp_output_filename != final_output_filename:
                    os.remove(temp_output_filename)
                
                derush_time = time.time() - start_derush_time
                logger.info(f"Dérushage terminé en {derush_time:.2f}s")
                
            except Exception as derush_error:
                logger.error(f"Erreur pendant le dérushage: {str(derush_error)}")
                # En cas d'échec du dérushage, utiliser la vidéo originale
                if output_path and os.path.exists(temp_output_filename):
                    import shutil
                    shutil.move(temp_output_filename, final_output_filename)
                else:
                    final_output_filename = temp_output_filename
                
                # Indiquer l'échec du dérushage dans la réponse
                if output_path:
                    return JSONResponse(
                        content={
                            "message": "Vidéo téléchargée mais dérushage échoué",
                            "error": str(derush_error),
                            "path": final_output_filename
                        },
                        status_code=200
                    )
        
        # Réponse personnalisée si un chemin de sortie est fourni
        if output_path:
            return JSONResponse(
                content={
                    "message": "Vidéo téléchargée et dérushée avec succès" if derush else "Vidéo téléchargée avec succès",
                    "path": final_output_filename
                },
                status_code=200
            )
        else:
            # Renvoyer directement le fichier
            return FileResponse(
                path=final_output_filename,
                filename=os.path.basename(final_output_filename),
                media_type="video/mp4",
                background=BackgroundTasks(cleanup_file, final_output_filename)
            )
            
    except Exception as e:
        logger.error(f"Erreur pendant le traitement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-and-derush")
async def upload_and_derush(
    file: UploadFile = File(...),
    min_silence_len: int = Form(1000),
    silence_thresh: int = Form(-50),
    max_thresh: int = Form(-10),
    margin_ms: int = Form(200)
):
    """
    Dérushe une vidéo existante uploadée.
    
    - **file**: Fichier vidéo à dérusher
    - **min_silence_len**: Longueur minimale d'un segment en ms
    - **silence_thresh**: Seuil de silence en dB
    - **max_thresh**: Seuil maximum en dB
    - **margin_ms**: Marge avant/après les segments en ms
    """
    try:
        # Vérifier que FFmpeg est installé
        if not check_ffmpeg_installed():
            raise HTTPException(
                status_code=500,
                detail="FFmpeg n'est pas installé ou n'est pas accessible"
            )
        
        # Générer un ID unique pour ce téléchargement
        upload_id = str(uuid.uuid4())
        
        # Sauvegarder le fichier uploadé
        temp_input_file = f"outputs/upload_{upload_id}.mp4"
        with open(temp_input_file, "wb") as f:
            f.write(await file.read())
        
        logger.info(f"Fichier uploadé sauvegardé: {temp_input_file}")
        
        # Dérusher la vidéo
        logger.info(f"Démarrage du dérushage de la vidéo uploadée")
        start_time = time.time()
        
        derushed_output = process_video(
            temp_input_file,
            min_silence_len,
            silence_thresh,
            max_thresh,
            margin_ms,
            log_progress
        )
        
        logger.info(f"Dérushage terminé en {time.time() - start_time:.2f}s")
        
        # Renvoyer la vidéo dérushée
        return FileResponse(
            path=derushed_output,
            filename=f"derushed_{file.filename}",
            media_type="video/mp4",
            background=BackgroundTasks(cleanup_files, [temp_input_file, derushed_output])
        )
        
    except Exception as e:
        logger.error(f"Erreur pendant le dérushage: {str(e)}")
        # Nettoyer le fichier temporaire en cas d'erreur
        try:
            if 'temp_input_file' in locals() and os.path.exists(temp_input_file):
                os.remove(temp_input_file)
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))

def cleanup_file(file_path):
    """Supprimer un fichier après qu'il ait été envoyé au client."""
    try:
        # Attendre pour s'assurer que le fichier est complètement envoyé
        time.sleep(60)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Fichier temporaire nettoyé: {file_path}")
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage du fichier {file_path}: {str(e)}")

def cleanup_files(file_paths):
    """Supprimer plusieurs fichiers après qu'ils aient été envoyés au client."""
    try:
        # Attendre pour s'assurer que les fichiers sont complètement envoyés
        time.sleep(60)
        for file_path in file_paths:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Fichier temporaire nettoyé: {file_path}")
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des fichiers: {str(e)}")

@app.on_event("startup")
async def startup_event():
    logger.info("Démarrage de l'API Derusher")
    
    # Vérifier les dépendances
    if not check_ffmpeg_installed():
        logger.warning("ATTENTION: FFmpeg n'est pas installé ou n'est pas accessible. Le dérushage ne fonctionnera pas.")
    
    # Planifier un nettoyage périodique des fichiers temporaires
    scheduler.add_job(lambda: cleanup_old_downloads("outputs", 24), "interval", hours=1)
    scheduler.start()
    
    # Exécuter un nettoyage initial
    cleanup_old_downloads("outputs", 24)

@app.on_event("shutdown")
async def shutdown_event():
    # Arrêter le planificateur
    scheduler.shutdown()
    logger.info("Arrêt de l'API Derusher")

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)