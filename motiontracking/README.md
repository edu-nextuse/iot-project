## motiontracking app voor IoT-project FysioFit ##

### Prerequisites ###
1. DE Pi5
2. USB camera

### Motiontracking omgeving ###
We maken uiteraard gebruik van een virtual enviroment. Voor onze omgeving heet deze: "miniforge3". Te activeren met "source ~/miniforge3/bin/activate"

Nu moeten we de Conda omgeving openen (Deze hadden we nodig om de opencv software te installeren) Dit doen we met "conda activate ultralytics-env"

Nu zijn we klaar om de software te runnen. Als je de software standalone wilt runnen is dit mogelijk met "cd Documents" en dan "./main.py" of "python3 main.py"

De software geeft wat errors, maar boot daarna een camera window met onze tracking software.

### Installatie ###
Verzoek de goden dat deze dag niet komt, maar mochten we de omgeving opnieuw moeten opzetten zijn hieronder de stappen:

1. lees "https://core-electronics.com.au/guides/how-to-set-up-yolo-computer-vision-on-a-raspberry-pi-conda-and-ultralytics/"
2. download miniforge3
3. installeer miniforge3
4. upgrade conda libraries (wederom pip is niet sterk genoeg. We hebben Conda nodig om opencv binnen te halen) 
 - conda install conda-libmamba-solver -y
 - conda config --set solver libmamba
5. installeer Ultralytics "conda create --name ultralytics-env python=3.11 -y"
6. activate conda env "conda activate ultralytics-env"
7.  Run main.py

### Motiontracking omgeving 2.0 anno 2026/06/02 ###
We willen de app gebruikersvriendelijk maken. Dit betekent dat de gebruiken niet een wiskundige hoeft te zijn om de motiontracking te kunnen starten. Hiervoor hebben we een oplossing:

#### Watcher ####
Watcher is een script dat de webserver in de gaten houdt. Wanneer de webserver aangeeft dat de gebruiker de camera nodig heeft, start watcher de app. Watcher wordt automatisch als systemctl gestart met het starten van de PI. Status van watcher is op te vragen met: "systemctl status watcher.service".

#### Alice fell down the rabbithole ####
Om de tracking software werkend te krijgen hebben we gebruik gemaakt van 'miniforge' en 'conda'. In beide gevallen hebben we venvs gemaakt om dit te hosten. Het is onduidelijk welke env nuttig is en welke niet, dus we gebruiken beide.

Het is lastig voor een gebruiker of voor watcher om hier in te duiken. Hiervoor hebben we uiteindelijk watcher verteld dat hij een andere python versie moet gebruiken om de motiontracking aan te spreken. Dit is: "/home/fysiofit/miniforge3/envs/ultralytics-env/bin/python3". Twee envs, 1 python instantie.

