# Derusher

Un outil pour télécharger des vidéos Loom et supprimer les silences (dérushage).

## Fonctionnalités

- 🌍 Téléchargement de vidéos Loom via une API REST (FastAPI)
- ✂️ Dérushage (suppression des silences) des vidéos
- 💻 Interface en ligne de commande (CLI)
- ℹ️ Support pour le dérushage de vidéos déjà téléchargées

> ***LE DISCORD 👉🏻 https://discord.gg/T6DCneUhD7***

## Prérequis

- Python 3.8 ou supérieur
- FFmpeg (requis pour le dérushage des vidéos)

## Installation

1. Cloner le dépôt :
```
git clone https://github.com/Chugyy/python-derusher.git
cd python-derusher
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
Voici un ajout détaillé sur la partie liée à **FFmpeg**, pour **Mac** *et* **Windows** :

---

## FFmpeg : Installation et Configuration (Mac & Windows)

### Qu'est-ce que FFmpeg ?

FFmpeg est un outil en ligne de commande ultra-puissant qui permet de traiter, convertir, extraire ou manipuler des fichiers audio et vidéo. Il est **indispensable** pour le dérushage, car il gère l’extraction audio, le découpage des segments vidéo, la concaténation, etc.

### Installation de FFmpeg

#### **Sur Mac 🍎**

##### 1. Avec Homebrew (méthode recommandée)

Si vous avez Homebrew (gestionnaire de paquets pour Mac), il suffit de lancer dans votre terminal :

```bash
brew install ffmpeg
```

* Homebrew s’occupe de tout.
* Pour vérifier l’installation, faites :

```bash
ffmpeg -version
```

* Si une version s’affiche, c’est tout bon !

##### 2. Sans Homebrew (méthode alternative)

* Rendez-vous sur [https://ffmpeg.org/download.html#build-mac](https://ffmpeg.org/download.html#build-mac)
* Téléchargez la dernière version pré-compilée ("Static build").
* Décompressez le dossier, copiez le fichier `ffmpeg` dans `/usr/local/bin` ou `/opt/homebrew/bin` (pour Apple Silicon) :

  ```bash
  sudo cp /chemin/vers/ffmpeg /usr/local/bin/
  sudo chmod +x /usr/local/bin/ffmpeg
  ```
* Vérifiez l’installation avec `ffmpeg -version`.

#### **Sur Windows 🪟**

##### 1. Téléchargement manuel (le plus simple)

* Allez sur [https://ffmpeg.org/download.html#build-windows](https://ffmpeg.org/download.html#build-windows)
  ou directement sur [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/)
* Téléchargez la version *release full build* (`ffmpeg-release-full.7z`).
* Extrayez le dossier ZIP ou 7z.
* Copiez le chemin du dossier `bin` (par exemple : `C:\ffmpeg\bin`).

##### 2. Ajouter FFmpeg au PATH

Pour que FFmpeg soit accessible dans **n'importe quel terminal** :

* Faites clic droit sur "Ce PC" > Propriétés > Paramètres système avancés > Variables d’environnement
* Dans “Variables système”, cherchez `Path` puis "Modifier"
* Cliquez sur "Nouveau" et collez le chemin du dossier `bin` de FFmpeg (par exemple : `C:\ffmpeg\bin`)
* Cliquez sur OK pour tout valider
* Fermez et rouvrez votre terminal, puis vérifiez avec :

  ```cmd
  ffmpeg -version
  ```

  Si la version s’affiche, c’est prêt !

---

### Problèmes fréquents

* **Commande "ffmpeg" introuvable ?**

  * Vérifiez que le binaire est bien dans le PATH système (voir ci-dessus).
  * Sous Mac : Fermez et rouvrez Terminal.
  * Sous Windows : Relancez l’invite de commandes après modification du PATH.
* **Permission denied sur Mac ?**

  * Ajoutez les droits d’exécution avec `chmod +x /usr/local/bin/ffmpeg`

### Utilisation dans le projet

* Le script Python fait appel à FFmpeg via des commandes système (`subprocess`).
* **Sans FFmpeg**, aucune étape de dérushage ne fonctionnera !
* Vous pouvez tester FFmpeg seul sur n’importe quelle vidéo :

  ```bash
  ffmpeg -i input.mp4 output.avi
  ```

  (pour convertir une vidéo en .avi, par exemple)

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

1. Lance le CLI :
```
python main.py
```

2. Choisis les options que tu veux :
    1. **Télécharger et dérusher une vidéo :** Colle une URL Loom
    2. **Dérusher une vidéo existante :** Mets un fichier vidéo dans `/temp` puis il apparaîtra dans les choix. (relance pour rafraîchir)

3. Col

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