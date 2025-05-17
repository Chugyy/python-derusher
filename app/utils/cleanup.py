import os
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("derusher-cleanup")

def cleanup_old_downloads(output_dir="outputs", max_age_hours=24):
    """
    Clean up old downloads in the outputs directory that are older than max_age_hours.
    
    Args:
        output_dir (str): Directory containing downloads
        max_age_hours (int): Maximum age in hours before files are deleted
    """
    if not os.path.exists(output_dir):
        logger.warning(f"Le dossier {output_dir} n'existe pas.")
        return
        
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    deleted_count = 0
    total_size = 0
    
    logger.info(f"Nettoyage des fichiers de plus de {max_age_hours} heures dans {output_dir}")
    
    for filename in os.listdir(output_dir):
        filepath = os.path.join(output_dir, filename)
        
        if os.path.isfile(filepath):
            file_stat = os.stat(filepath)
            file_age = now - file_stat.st_mtime
            
            if file_age > max_age_seconds:
                file_size = os.path.getsize(filepath)
                total_size += file_size
                
                try:
                    os.remove(filepath)
                    deleted_count += 1
                    logger.info(f"Supprimé: {filename} (âge: {file_age/3600:.1f}h, taille: {file_size/1048576:.1f}MB)")
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression de {filename}: {str(e)}")
    
    if deleted_count > 0:
        logger.info(f"Nettoyage terminé: {deleted_count} fichiers supprimés, {total_size/1048576:.1f}MB libérés")
    else:
        logger.info("Aucun fichier à nettoyer") 