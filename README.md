# Derusher

Un outil pour télécharger des vidéos Loom et supprimer les silences (dérushage).

## Fonctionnalités

- Téléchargement de vidéos Loom via une API REST (FastAPI)
- Dérushage (suppression des silences) des vidéos
- Interface en ligne de commande (CLI)
- Support pour le dérushage de vidéos déjà téléchargées

## Prérequis

- Python 3.8 ou supérieur
- FFmpeg (requis pour le dérushage des vidéos)

## Installation

1. Cloner le dépôt :
```
git clone <repository-url>
cd derusher
```

2. Créer et activer un environnement virtuel (recommandé) :
```
python -m venv venv
source venv/bin/activate  # Sur Windows : venv\Scripts\activate
```

3. Installer les dépendances :
```
pip install -r requirements.txt
```

4. S'assurer que FFmpeg est installé et accessible depuis le PATH du système.

## Utilisation

### Serveur API

Lancer le serveur API :
```
python server.py
```

Le serveur sera accessible à l'adresse http://localhost:8000.

Endpoints disponibles :
- `GET /` : Page d'accueil
- `GET /check` : Vérifier les dépendances
- `GET /download` : Télécharger et optionnellement dérusher une vidéo Loom
- `POST /upload-and-derush` : Dérusher une vidéo uploadée

Documentation interactive de l'API : http://localhost:8000/docs

### Interface en ligne de commande (CLI)

Le CLI offre plusieurs façons d'utiliser l'outil :

1. Mode interactif :
```
python main.py
```

2. Télécharger et dérusher une vidéo :
```
python main.py download <URL>
```

3. Télécharger sans dérusher :
```
python main.py download <URL> --no-derush
```

4. Dérusher une vidéo existante :
```
python main.py derush <chemin-video>
```

5. Lister les vidéos disponibles dans le répertoire temp :
```
python main.py list
```

## Structure du projet

```
final/
├── app/
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── cleanup.py
│   │   └── file_handler.py
│   ├── __init__.py
│   ├── derusher.py
│   └── loom_downloader.py
├── outputs/         # Dossier pour les fichiers générés
├── temp/            # Dossier pour les fichiers temporaires
├── README.md
├── requirements.txt
├── server.py        # Serveur FastAPI
└── main.py          # Interface CLI
```

## Comment ça fonctionne

### Téléchargement de vidéos Loom

L'outil utilise une technique avancée pour extraire et télécharger les flux HLS (HTTP Live Streaming) de Loom. Il télécharge séparément les flux audio et vidéo, puis les fusionne en une seule vidéo MP4.

### Dérushage

Le dérushage est effectué en plusieurs étapes :
1. Extraction de l'audio de la vidéo
2. Analyse de l'audio pour détecter les segments non silencieux
3. Découpage de la vidéo en segments non silencieux
4. Concaténation des segments pour créer la vidéo finale dérushée

## Dépannage

1. **Problème de téléchargement** : Vérifiez que l'URL Loom est valide et accessible.

2. **Problème de dérushage** : Vérifiez que FFmpeg est correctement installé (`ffmpeg -version`).

3. **Serveur inaccessible** : Vérifiez que le serveur est en cours d'exécution (`python server.py`).

## Licence

Ce projet est open source. 