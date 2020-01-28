#!/usr/bin/env python3

import os
import trolly
import json
import re
import os.path
import mimetypes
import requests
import locale
import time

from easygui import *
from slugify import slugify
from markdown2 import markdown, markdown_path
from weasyprint import HTML, CSS
from datetime import datetime
from tqdm import tqdm
from string import Template

def check_card_in_printed_list(card_id, printed_cards_list_file_name):
    if not os.path.isfile(printed_cards_list_file_name):
        return False

    with open(printed_cards_list_file_name) as data_file:
        printed_list = json.load(data_file)
        return card_id in printed_list

def add_card_to_printed_list(card_id, printed_cards_list_file_name):
    if not os.path.isfile(printed_cards_list_file_name):
        printed_list = []
    else:    
        with open(printed_cards_list_file_name) as data_file:
            printed_list = json.load(data_file)

    if not card_id in printed_list:
        printed_list.append(card_id) 

    with open(printed_cards_list_file_name, 'w') as data_file:
        json.dump(printed_list, data_file, indent=2)

def select_board(client):
    boards = client.get_boards()
    board_names = list(map(lambda board: '{} [{}]'.format(board.name, board.id), boards))
    selected_board = choicebox('Select your board', 'Boards', board_names)

    return re.search('\[(.*)\]', selected_board, re.IGNORECASE).group(1)

def select_list(client, board_id):
    board = client.get_board(board_id)
    lists = board.get_lists()
    list_names = list(map(lambda list: '{} [{}]'.format(list.name, list.id), lists))
    selected_list = choicebox('Select your list', 'Lists', list_names)

    return re.search('\[(.*)\]', selected_list, re.IGNORECASE).group(1)

def build_card(card_info):
    if 'labels' in card_info:
        label_names = [l['name'] for l in card_info['labels']]
    else:
        label_names = []

    return {
        'id': card_info['id'],
        'name': card_info['name'],
        'desc': card_info['desc'].split('---', 1)[0],
        'labels': label_names
    }

def create_story_cards_pdf(client, board_id, list_id, generated_dir, printed_cards_list_file_name):
    bad_cards = []
    board = client.get_board(board_id)

    target_list = None
    for list in board.get_lists():
        if list.id == list_id:
            target_list = list

    if target_list == None:
        msgbox("No list found!")
        return

    num_pdfs = 0  
    skipped_pdfs = 0    
    for card in tqdm(target_list.get_cards()):
        card_info = build_card(card.get_card_information())

        footer = ''
        if len(card_info['labels']) > 0:
            footer = card_info['labels'][0]

        if not check_card_in_printed_list(card_info['id'], printed_cards_list_file_name) or not ynbox('Card "{}" has already been printed, shall I skip this card?'.format(card_info['name'])):
            create_story_card_pdf(card_info['name'], card_info['desc'], footer, generated_dir)
            add_card_to_printed_list(card_info['id'], printed_cards_list_file_name)
            num_pdfs = num_pdfs + 1
        else:
            skipped_pdfs = skipped_pdfs + 1

    return num_pdfs, skipped_pdfs

def get_css():
    return CSS(string='''
@page {
    size: A4 landscape; 
    margin: 0.25cm;
}

* {
    font-family: Sans-Serif;
}

h1, h2, h3 {
    text-align: center;
    font-weight: 200;
}

h1 {
    font-size: 48px;
}

h2 {
  font-size: 30px;
  position: fixed;
  left: 0;
  bottom: 0;
  width: 100%;
  text-align: center;
}

p {
    font-size: 36px;
}
''')

def get_template():
    return Template("""# $title

$text

## $footer
""")

def create_story_card_pdf(title, text, footer, generated_dir):
    pdf_file_path = "{}/{}.pdf".format(generated_dir, slugify(title, to_lower=True))
    locale.setlocale(locale.LC_ALL, "C.UTF-8")
    raw_markdown = get_template().substitute({ 'title': title, 'text': text, 'footer': footer})
    raw_html = markdown(raw_markdown)
    HTML(string=raw_html, base_url=generated_dir).write_pdf(pdf_file_path, stylesheets=[get_css()])

def start_up():
    current_dir = os.path.dirname(os.path.realpath(__file__))
    generated_dir = current_dir + '/pdf'
    config_dir = current_dir + '/config'

    if not os.path.exists(generated_dir):
        os.makedirs(generated_dir)

    if len(os.listdir(generated_dir + '/')) > 0:
        if ynbox('Found generated files in target dir, shall I delete them?'):
            for file in os.listdir(generated_dir + '/'):
                os.remove(generated_dir + '/' + file)

    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    config_file = config_dir + '/config.json'

    if not os.path.isfile(config_file):
        fieldValues = multenterbox('Enter your Tello API data, needed for fetching cards from trello', 'Trello API Data', ['apiKey','serverToken'])
        config_data = {
            'apiKey': fieldValues[0],
            'serverToken': fieldValues[1]
        }

        with open(config_file, 'w') as data_file:
            json.dump(config_data, data_file, indent=2)

    with open(config_file) as data_file:
        config = json.load(data_file)

    client = trolly.client.Client(config['apiKey'], config['serverToken'])

    return current_dir, generated_dir, client, config_dir +  '/printed_cards.json'

def main():
    msgbox('Welcome to the eSagu Trello card printer')
    current_dir, generated_dir, client, printed_cards_list_file_name = start_up()

    board_id = select_board(client)
    list_id = select_list(client, board_id)
    num_pdfs, skipped_pdfs = create_story_cards_pdf(client, board_id, list_id, generated_dir, printed_cards_list_file_name)
    msgbox('Created {} PDF file(s) in "{}", skipped {} cards.'.format(num_pdfs, generated_dir, skipped_pdfs))

if __name__ == "__main__":
    main()