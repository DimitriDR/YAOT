import json
import os
import signal
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from os import getenv

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

mark_json_path = "/app/marks.json"
"""Variable globale contenant les notes. Fichier uniquement manipulé par le programme. Pas bien, je sais."""

send_with_signal: bool = True
"""Variable pour activer ou désactiver l'envoi de messages par Signal."""


def signal_handler(signal, frame):
    print("Signal d'arrêt reçu, fin de l'application...")
    exit(0)


def get_formatted_datetime() -> str:
    """
    Fonction permettant de récupérer la date et l'heure actuelle sous forme de chaîne de caractères.
    :return: Chaîne de caractères représentant la date et l'heure actuelle.
    """
    return datetime.now().strftime("%d/%m/%Y - %H:%M:%S")


def send_signal_message(message: str) -> tuple[int, str]:
    """
    Fonction permettant d'envoyer un message à un numéro de téléphone par Signal.
    :param message: Message à envoyer.
    :return: Code retourné par la requête HTTP et contenu de la réponse.
    """
    url: str = getenv("SIGNAL_API_SERVER") + "/v2/send"

    headers = {"Content-Type": "application/json"}
    data = {
        "message": message,
        "number": getenv("PHONE_NUMBER"),
        "recipients": [
            getenv("PHONE_NUMBER")
        ],
        "text_mode": "styled"
    }

    response = requests.post(url, headers=headers, json=data)

    return response.status_code, response.text


def get_number_of_tests(html_content: BeautifulSoup) -> int:
    """
    Fonction permettant de récupérer le nombre d'épreuves déjà notées.
    :param html_content: Contenu HTML de la page de l'OASIS.
    :return: Nombre d'épreuves déjà notées.
    """
    tests_content: str = html_content.find(id=f"TestsSemester{getenv("OASIS_ID")}_{datetime.now().year - 1}_{getenv("SEMESTER")}").get_text()
    number_of_tests: int = int(tests_content.split("(")[1].split(")")[0])

    return number_of_tests


def get_oasis_page() -> BeautifulSoup:
    """
    Fonction permettant de récupérer le contenu de la page de l'OASIS.
    :return: Contenu HTML de la page d'OASIS.
    """
    url: str = "https://oasis.polytech.universite-paris-saclay.fr/#codepage=MYMARKS"

    webdriver_service = Service("/usr/bin/chromedriver")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    with webdriver.Chrome(service=webdriver_service, options=chrome_options) as browser:
        browser.get(url)
        login_input = browser.find_element(By.XPATH, '//input[@placeholder="Identifiant"]')
        login_input.send_keys(str(getenv("OASIS_ID")))
        password_input = browser.find_element(By.XPATH, '//input[@placeholder="Mot de passe"]')
        password_input.send_keys(getenv("OASIS_PASSWORD"))

        login_button = browser.find_element(By.XPATH, '//button[@type="submit"]')
        login_button.click()

        WebDriverWait(browser, 25).until(EC.presence_of_element_located((By.ID, "Semester21900789_2022_1")))

        soup = BeautifulSoup(browser.page_source, "html.parser")

    return soup


def get_marks(html_content: BeautifulSoup) -> dict:
    """
    Fonction permettant de récupérer les notes et les matières actuelles de l'utilisateur.
    :param html_content: Contenu HTML de la page d'OASIS.
    :return: Dictionnaire associant une matière avec son nombre de notes.
    """
    # Logiquement, on récupère le tableau des notes et donc les lignes
    table = html_content.find(id="Tests12023")
    tbody = table.find("tbody")
    rows = tbody.find_all("tr")

    # On initialise un dictionnaire pour stocker les matières et le nombre de notes
    current_marks: dict = {}

    # Pour chacune des lignes, on récupère le nom de la matière, le nom de l'épreuve et la note
    for row in rows:
        tds = row.find_all("td")

        subject_name: str = (tds[0].get_text().split(" — ")[1]).rstrip()
        test_name: str = tds[1].get_text().rstrip()

        try:
            grade: float = float(tds[3].get_text().replace(",", "."))
        except ValueError:
            grade: str = tds[3].get_text().rstrip()

        if subject_name not in current_marks:
            current_marks[subject_name] = {test_name: grade}
        else:
            current_marks[subject_name][test_name] = grade

    return current_marks


def initial_setup(html_content: BeautifulSoup):
    """
    Fonction chargée de l'initialisation de l'application, c'est-à-dire de récupérer le nombre de notes déjà présentes
    ainsi que les matières, contrôles et notes associées pour les comparer avec les futures notes.
    :return: None
    """
    # Vérification des variables d'environnement
    if "OASIS_ID" not in os.environ or os.environ["OASIS_ID"] == "":
        print(f"{get_formatted_datetime()} -- [ERROR] La variable d'environnement OASIS_ID n'est pas définie. "
              f"Impossible de continuer sans identifiant.")
        exit(1)

    if "OASIS_PASSWORD" not in os.environ or os.environ["OASIS_PASSWORD"] == "":
        print(f"{get_formatted_datetime()} -- [ERROR] La variable d'environnement OASIS_PASSWORD n'est pas définie. "
              f"Impossible de continuer sans mot de passe.")
        exit(1)

    if "SIGNAL_API_SERVER" not in os.environ or os.environ["SIGNAL_API_SERVER"] == "":
        print(f"{get_formatted_datetime()} -- [WARN] La variable d'environnement SIGNAL_API_SERVER n'est pas définie. "
              f"Il sera impossible d'envoyer des messages par Signal")
        global send_with_signal
        send_with_signal = False
    if "PHONE_NUMBER" not in os.environ or os.environ["PHONE_NUMBER"] == "":
        print(f"{get_formatted_datetime()} -- [WARN] La variable d'environnement PHONE_NUMBER n'est pas définie. "
              f"Il sera impossible d'envoyer des messages par Signal")
        send_with_signal = False

    print(f"{get_formatted_datetime()} -- [INFO] Début de l'initialisation...")
    current_number_of_tests: int = get_number_of_tests(html_content)
    current_marks: dict = get_marks(html_content)

    print(
        f"{get_formatted_datetime()} -- [INFO] Toutes les informations ont été récupérées, "
        f"écriture dans le fichier JSON..."
    )

    update_json(current_marks, current_number_of_tests)

    print(f"{get_formatted_datetime()} -- [INFO] Initialisation terminée...")


def update_json(current_marks, current_number_of_tests):
    with open(mark_json_path, "w") as file:
        file.write("{\n")
        file.write(f"\t\"tests\": {current_number_of_tests},\n\t\"marks\": ")
        json.dump(current_marks, file, indent=4, ensure_ascii=False)
        file.write("\n}")


def compare_old_and_new_marks(html_content, marks_data) -> tuple[dict, dict]:
    """
    Fonction chargée de comparer les anciennes notes avec les nouvelles.
    :param html_content: Contenu HTML de la page d'OASIS.
    :param marks_data: Dictionnaire contenant les notes actuelles.
    :return: Dict
    """
    marks: dict = get_marks(html_content)
    """Liste des notes telles qu'elles sont actuellement sur OASIS."""

    new_marks: dict = {}
    """Liste des nouvelles notes que la fonction va remplir et retourner."""

    # On compare les anciennes notes stockées dans le fichier JSON avec celles que l'on vient de recevoir
    for subject in marks:
        # Si la matière n'est pas dans le fichier JSON, c'est qu'il y a une nouvelle note inédite
        if subject not in marks_data["marks"]:
            for test in marks[subject]:
                new_marks[subject] = {test: marks[subject][test]}
        else:  # Sinon, on regarde les tests déjà présents par rapport aux nouvelles notes
            for test in marks[subject]:
                # Si le test n'est pas dans le fichier JSON, c'est qu'il y a une nouvelle note inédite
                if test not in marks_data["marks"][subject]:
                    new_marks[subject] = {test: marks[subject][test]}

    return marks, new_marks


def send_email(email_address: str, message: str):
    """
    Fonction permettant d'envoyer un e-mail.
    :param email_address: Adresse e-mail du destinataire.
    :param message: Message à envoyer.
    :return:
    """
    email: str = getenv("EMAIL_FROM")
    password: str = getenv("EMAIL_PASSWORD")

    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587

    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(email, password)

    msg = MIMEMultipart()
    msg["From"] = email
    msg["To"] = email_address
    msg["Subject"] = "🤖  Nouvelle note sur OASIS"

    html_message = f"<html><body><p>{message}</p></body></html>"
    msg.attach(MIMEText(html_message, "html"))

    server.send_message(msg)
    server.quit()


def send_emails(subject, test):
    """
    Fonction permettant d'envoyer un e-mail aux utilisateurs volontaires
    :param subject: Nom de la matière concernée par la note.
    :param test: Nom de l'épreuve concernée par la note.
    :return: Néant. Envoi d'e-mails.
    """
    emails = getenv("EMAILS").split(",")

    for email in emails:
        message: str = (f"Nouvelle note pour la matière « <strong>{subject}</strong> » pour l'épreuve « {test} »<br "
                        f"/><br /><a href='https://oasis.polytech.universite-paris-saclay.fr' target='_blank'>LIEN "
                        f"VERS OASIS</a><br/><br/><i>Puisse le sort vous "
                        f"être favorable... 🦅</i>")
        send_email(email, message)


def new_mark_routine(html_content: BeautifulSoup, marks_data: dict):
    """
    Fonction permettant de gérer une nouvelle note.
    :param html_content: Contenu HTML de la page d'OASIS.
    :param marks_data: Dictionnaire contenant les notes actuelles.
    :return:
    """
    whole_new_marks, new_marks_only = compare_old_and_new_marks(html_content, marks_data)

    for subject in new_marks_only:
        for test in new_marks_only[subject]:
            message: str = f"Nouvelle note pour la matière « {subject} » : **{new_marks_only[subject][test]}/20** pour l'épreuve « *{test}* »"

            # Envoi d'un message Signal pour le king
            if send_with_signal:
                signal_status_code = send_signal_message(message)
                if signal_status_code[0] != 201:
                    print(f"{get_formatted_datetime()} -- [ERREUR] Impossible d'envoyer le message Signal : "
                          f"{signal_status_code[1]}")
                else:
                    print(f"{get_formatted_datetime()} -- [INFO] Message Signal envoyé avec succès !")

            # Envoi d'un e-mail pour le peuple
            send_emails(subject, test)

    # Une fois qu'on a la liste des nouvelles notes, on peut mettre à jour le fichier JSON
    number_of_tests: int = get_number_of_tests(html_content)

    update_json(whole_new_marks, number_of_tests)


def update_routine():
    """
    Fonction permettant de mettre à jour les notes.
    :return: Néant. Mise à jour des notes.
    """
    print(f"{get_formatted_datetime()} -- [INFO] Recherche de nouvelles notes...")
    html_content: BeautifulSoup = get_oasis_page()

    # On regarde s'il y a une nouvelle note en regardant le nombre d'épreuves
    number_of_tests: int = get_number_of_tests(html_content)

    # Puis en comparant avec la valeur stockée dans le fichier JSON
    with open(mark_json_path, "r") as file:
        marks_data: dict = json.load(file)
        previous_number_of_tests: int = marks_data["tests"]

    # Si le nombre d'épreuves a augmenté, on récupère les nouvelles notes
    if number_of_tests > previous_number_of_tests:
        print(f"{get_formatted_datetime()} -- [INFO] Une ou plusieurs nouvelles notes détectées !")
        new_mark_routine(html_content, marks_data)
    else:
        print(f"{get_formatted_datetime()} -- [INFO] Pas de nouvelle note...")


def main():
    """
    Fonction principale du programme chargée de lancer les différentes routines.
    S'assure également que le programme ne tourne pas la nuit pour éviter les requêtes inutiles.
    """
    now = datetime.now()
    opening_hour: int = 6
    closing_hour: int = 23

    # Si l'heure actuelle est comprise entre la plage horaire, on lance le programme
    if opening_hour <= now.hour <= closing_hour:
        # On accepte le dernier lancement vers 23 h, mais après, on ferme boutique, on prend 10 minutes de marge
        if now.hour == closing_hour and now.minute > 10:
            print(f"{get_formatted_datetime()} -- [INFO] ZzZzZz ! Le programme dort... À demain dès {opening_hour} h !")
            return

        # Si le fichier de note n'existe pas, on définit le booléen à vrai pour effectuer la configuration initiale
        skip_initial_setup: bool = os.path.exists(mark_json_path) and os.stat(mark_json_path).st_size != 0

        oasis_page = get_oasis_page()

        if not skip_initial_setup:
            initial_setup(oasis_page)
        else:
            update_routine()
    else:
        print(f"{get_formatted_datetime()} -- [INFO] ZzZzZz ! Le programme dort... À demain dès {opening_hour} h !")


signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    main()
