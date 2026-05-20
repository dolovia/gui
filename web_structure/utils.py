import json
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from termcolor import colored
from functools import lru_cache
from typing import Optional

def _has_results_markers(soup: BeautifulSoup) -> bool:
    markers = [
        "information de l'ouvrant droit",
        "information du bénéficiaire",
        "information du bénéficiaire des soins",
        "information du b\xe9n\xe9ficiaire",
        "ouverture des droits",
        "droits et couvertures",
    ]
    for marker in markers:
        if soup.find(string=lambda t: t and marker in t.lower()):
            return True
    return False


def parse_rights_data(html_content: str) -> Optional[dict]:
    """
    Parses the HTML content of the "Consultation des Droits" page
    and transforms it into a structured dictionary.

    Args:
        html_content: A string containing the HTML of the page.

    Returns:
        A dictionary with the extracted and structured data.
    """
    if not html_content:
        return None
    soup = BeautifulSoup(html_content, 'html.parser')
    if not _has_results_markers(soup):
        return None

    data = {}

    # Helper to extract value from a "Label : Value" text format
    def get_value_from_label(element):
        if not element:
            return None
        text = element.get_text(" ", strip=True)
        if ':' in text:
            return text.split(':', 1)[1].strip()
        return text or None

    # Helper to find a label and extract its associated value from the next text node
    def find_value_after_label(label_text):
        label_node = soup.find(string=lambda t: t and label_text in t)
        if not label_node:
            return None
        label_text_value = label_node.strip()
        if ':' in label_text_value:
            after = label_text_value.split(':', 1)[1].strip()
            if after:
                return after
        label_tag = label_node.parent if hasattr(label_node, 'parent') else None
        if label_tag:
            td = label_tag.find_parent('td') or label_tag
            if td:
                next_td = td.find_next_sibling('td')
                if next_td:
                    return next_td.get_text(" ", strip=True)
        if label_tag and label_tag.next_sibling and isinstance(label_tag.next_sibling, str):
            return label_tag.next_sibling.strip()
        return None

    # 1. Consultation Information
    data['consultation'] = {
        'date_soins': find_value_after_label('Date des soins :'),
        'identifiant_nir': find_value_after_label('Identifiant (NIR) :')
    }

    # 2. Ouvrant Droit (Policy Holder)
    ouvrant_droit = {}
    od_header = soup.find(
        lambda tag: tag.name in ('font', 'td', 'span', 'b', 'strong')
        and "information de l'ouvrant droit" in tag.get_text().lower()
    )
    if od_header:
        current_tr = od_header.find_parent('tr')
        nom_tr = current_tr.find_next_sibling('tr') if current_tr else None
        usage_tr = nom_tr.find_next_sibling('tr') if nom_tr else None
        prenom_tr = usage_tr.find_next_sibling('tr') if usage_tr else None
        
        ouvrant_droit['nom_famille'] = get_value_from_label(nom_tr.find('td')) if nom_tr else None
        ouvrant_droit['nom_usage'] = get_value_from_label(usage_tr.find('td')) if usage_tr else None
        ouvrant_droit['prenom'] = get_value_from_label(prenom_tr.find('td')) if prenom_tr else None
    data['ouvrant_droit'] = ouvrant_droit

    # 3. Bénéficiaire (Beneficiary)
    beneficiaire = {}
    ben_header = soup.find(
        lambda tag: tag.name in ('font', 'td', 'span', 'b', 'strong')
        and "information du bénéficiaire des soins" in tag.get_text().lower()
    )
    if ben_header:
        current_tr = ben_header.find_parent('tr')
        nom_tr = current_tr.find_next_sibling('tr') if current_tr else None
        prenom_tr = nom_tr.find_next_sibling('tr') if nom_tr else None
        dob_tr = prenom_tr.find_next_sibling('tr') if prenom_tr else None

        beneficiaire['nom_famille'] = get_value_from_label(nom_tr.find('td')) if nom_tr else None
        beneficiaire['prenom'] = get_value_from_label(prenom_tr.find('td')) if prenom_tr else None
        
        dob_text = get_value_from_label(dob_tr.find('td')) if dob_tr else None
        # Handle non-breaking spaces before splitting
        dob_parts = dob_text.replace('\xa0', ' ').split() if dob_text else []
        beneficiaire['date_naissance'] = dob_parts[0] if dob_parts else None
        beneficiaire['rang'] = dob_parts[1] if len(dob_parts) > 1 else None
    data['beneficiaire'] = beneficiaire

    # 4. Organisme de Gestion (Managing Organization)
    organisme_gestion = {}
    code_label = soup.find(string=lambda t: t and "code grand régime" in t.lower())
    if code_label:
        gestion_table = code_label.parent.find_parent('table')
        if gestion_table:
            rows = gestion_table.find_all('tr')
            
            if len(rows) >= 2:
                cells_r1 = rows[0].find_all('td')
                if len(cells_r1) >= 4:
                    organisme_gestion['code_grand_regime'] = get_value_from_label(cells_r1[0])
                    organisme_gestion['caisse_gestionnaire'] = get_value_from_label(cells_r1[1])
                    paiement_text = get_value_from_label(cells_r1[2])
                    paiement_parts = paiement_text.split() if paiement_text else []
                    organisme_gestion['centre_paiement'] = paiement_parts[0] if len(paiement_parts) > 0 else None
                    organisme_gestion['cle_paiement'] = paiement_parts[1] if len(paiement_parts) > 1 else None
                    organisme_gestion['code_gestion'] = get_value_from_label(cells_r1[3])

                cells_r2 = rows[1].find_all('td')
                if len(cells_r2) >= 3:
                    organisme_gestion['centre_gestion'] = get_value_from_label(cells_r2[2])
    data['organisme_gestion'] = organisme_gestion
    # 5. Droits et Couvertures (Rights and Coverage)
    droits_couvertures = {}
    img_element = soup.find('img', {'src': 'images/bt_vert.gif'})
    rights_table = img_element.find_parent('table') if img_element else None
    if not rights_table:
        rights_header = soup.find(string=lambda t: t and "Droits" in t and "Couvertures" in t)
        if rights_header:
            rights_table = rights_header.parent.find_parent('table')
    if rights_table:
        for row in rights_table.find_all('tr'):
            cells = row.find_all('td')
            if not cells or len(cells) < 3:
                continue

            status_img = cells[0].find('img') if cells else None
            status_src = status_img['src'] if status_img and status_img.has_attr('src') else ''

            label_text = cells[1].get_text(strip=True)
            value_text = cells[2].get_text(strip=True)
            is_active = 'bt_vert.gif' in status_src if status_src else None

            if "ouverture des droits" in label_text.lower():
                if is_active is None:
                    item = {'statut': value_text}
                else:
                    item = {'statut': "Ouverts" if is_active else "Fermés"}
                if is_active:
                    parts = value_text.split()
                    item['periode_debut'] = parts[1]
                    item['periode_fin'] = parts[3]
                droits_couvertures['regime_base'] = item
            
            elif "exonération du ticket modérateur" in label_text.lower():
                droits_couvertures['exoneration_ticket_moderateur'] = {'statut': value_text}
            
            elif "modulation du ticket modérateur" in label_text.lower():
                droits_couvertures['modulation_ticket_moderateur'] = {'statut': value_text}
            
            elif "complémentaire santé solidaire" in label_text.lower():
                if is_active is None:
                    item = {'statut': value_text}
                else:
                    item = {'statut': "Ouverts" if is_active else "Fermés"}
                if is_active:
                    parts = value_text.split()
                    item['periode_debut'] = parts[1]
                    item['periode_fin'] = parts[3]
                droits_couvertures['complementaire_sante_solidaire'] = item
            
            elif "médecin traitant" in label_text.lower():
                item = {'statut': value_text}
                if value_text == 'OUI':
                    details_row = row.find_next_sibling('tr')
                    if details_row:
                        details_cells = details_row.find_all('td')
                        if len(details_cells) >= 3:
                            name_text = details_cells[1].get_text().replace('\xa0', ' ').strip()
                            num_text = get_value_from_label(details_cells[2])
                            
                            name_parts = name_text.split()
                            item['nom'] = name_parts[2] if len(name_parts) > 2 else None
                            item['prenom'] = name_parts[5] if len(name_parts) > 5 else None
                            item['numero'] = num_text
                droits_couvertures['medecin_traitant'] = item
    data['droits_et_couvertures'] = droits_couvertures

    return data



def alterative_fetch_post(driver, beneficiary_name, usual_name, first_name, birth_date, nir, event_value_override=None, timeout=30):
    """
    Fetch alternative data using the tableauActionLoupePQ endpoint.
    This is called when multiple candidates are found.
    Uses modern fetch API instead of XMLHttpRequest.
    
    Args:
        driver: Selenium webdriver instance
        beneficiary_name: Name of beneficiary
        usual_name: Usual name
        first_name: First name
        birth_date: Birth date (format: DDMMYYYY)
        nir: NIR number (will be validated and fixed if needed)
        timeout: Script timeout in seconds (default: 30)
    
    Returns:
        HTML response from the server or None if error
    """
    # Validate and fix NIR format
    nir_cleaned = ''.join(c for c in str(nir) if c.isdigit())
    
    if len(nir_cleaned) == 15:
        print(colored(f"NIR {nir} has 15 digits, truncating to first 13 digits", "yellow"))
        nir_cleaned = nir_cleaned[:13]
    elif len(nir_cleaned) == 14:
        print(colored(f"NIR {nir} has 14 digits, using first 13", "yellow"))
        nir_cleaned = nir_cleaned[:13]
    
    # Compose the eventValue string as in the curl example
    event_value = event_value_override or f"{beneficiary_name}{usual_name}{first_name}{birth_date}{nir_cleaned}"
    
    # Properly URL-encode the payload
    payload = urlencode({
        "actionTableau": "selectpuceimg###eventValue",
        "eventValue": event_value
    })
    
    print(colored(f"Alternative fetch - Beneficiary: {beneficiary_name}, Event value base: {event_value}", "cyan"))

    # JavaScript code to perform the fetch request using modern API
    fetch_script = f"""
    var callback = arguments[arguments.length - 1];
    var payload = arguments[0];
    
    var url = 'https://portail.sesam-vitale.fr/cdr/amo/CNAM/PQ_J/tableauActionLoupePQ.do';
    
    console.log('Alternative fetch starting with payload:', payload);
    
    fetch(url, {{
        method: 'POST',
        credentials: 'include',
        headers: {{
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9'
        }},
        body: payload,
        mode: 'same-origin'
    }}).then(function(resp) {{
        console.log('Alternative fetch response status:', resp.status);
        if (!resp.ok) {{
            return resp.text().then(function(errText) {{
                throw new Error('Request failed: ' + resp.status + ' ' + resp.statusText);
            }});
        }}
        return resp.text();
    }}).then(function(html) {{
        console.log('Alternative fetch received HTML (' + html.length + ' bytes)');
        callback(html);
    }}).catch(function(err) {{
        console.error('Alternative fetch failed:', err);
        callback('Error: ' + err.message);
    }});
    """
    
    # Execute the fetch request in the browser context
    try:
        original_timeout = driver.execute_script("return window.asyncScriptTimeout") or 30000
        driver.set_script_timeout(timeout)
        response = driver.execute_async_script(fetch_script, payload)
        driver.set_script_timeout(original_timeout / 1000)  # Reset to original
    except Exception as e:
        print(colored(f"Timeout or error in alternative fetch: {str(e)}", "red"))
        return None
    
    if isinstance(response, str) and response.startswith('Error'):
        print(colored(f"Error in alternative fetch: {response}", "red"))
        return None
    
    print(colored(f"Alternative fetch successful - received {len(response) if response else 0} bytes", "green"))
    return response

# --- Main execution block ---
if __name__ == "__main__":
    try:
        with open('data.html', 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Get the structured data
        parsed_data = parse_rights_data(html_content)

        # Convert to formatted JSON and print
        json_output = json.dumps(parsed_data, indent=2, ensure_ascii=False)
        print(json_output)

    except FileNotFoundError:
        print("Error: 'data.html' not found. Make sure the file is in the same directory as the script.")
    except Exception as e:
        print(f"An error occurred: {e}")
