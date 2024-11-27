===============
SPOTS-IN-YEASTS
===============


- Le working directory peut être vide au départ.
  Des dossiers vont être créés pour chaque élément sauvegardé à l'intérieur.
    - "channels-layouts": Dossier qui stock les JSON qui décrivent les configurations de canaux.
    - "spots-configs": Dossier qui stock les JSON qui décrivent les settings de segmentation des spots.

- Ajouter un champ de texte dans le "ChannelsLayoutEditor" qui demande le nom de cette configuration.
  On voudra passer le working_directory dans les paramètres du constructeur et ne pas ouvrir de fenêtre.
  Si le working directory n'est pas défini, on ne veut pas ouvrir l'outil.

- Quand un nouveau layout est créé, on veut refresh la combobox qui en donne une preview.
  Il faudrait même qu'il soit loaded d'office.

- Quand le working directory est défini, on veut le probe pour refresh tout ce qui est affiché.
  La notion de working directory sera importante pour sauvegarder les fichiers de contrôle.

- Ajouter un bouton "From existing config" dans le "ChannelsLayoutEditor".
  Ce bouton ouvrira une fenêtre qui permettra de choisir un fichier JSON existant.
  On veut que le layout soit chargé dans l'éditeur, et permet de se baser dessus pour en créer un nouveau.