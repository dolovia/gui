import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from termcolor import colored
from functools import lru_cache
from typing import Optional, Callable

_logger: Optional[Callable[[str], None]] = None
_use_color = True


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    text = str(value).replace("\xa0", " ")
    text = text.replace("´", "'").replace("’", "'").replace("`", "'")
    text = " ".join(text.split())
    return text.strip().lower()


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split())


def set_logger(logger: Optional[Callable[[str], None]] = None, use_color: bool = True) -> None:
    global _logger, _use_color
    _logger = logger
    _use_color = use_color


def _log(message: str, color: Optional[str] = None) -> None:
    text = colored(message, color) if _use_color and color else message
    if _logger:
        _logger(text)
    else:
        print(text)

def _has_results_markers(soup: BeautifulSoup) -> bool:
    markers = [
        "information de l'ouvrant droit",
        "information du bénéficiaire",
        "information du bénéficiaire des soins",
        "information du b\xe9n\xe9ficiaire",
        "ouverture des droits",
        "droits et couvertures",
    ]
    normalized_markers = [_normalize_text(marker) for marker in markers]

    def has_marker(text: Optional[str]) -> bool:
        if not text:
            return False
        normalized = _normalize_text(text)
        return any(marker in normalized for marker in normalized_markers)

    return soup.find(string=has_marker) is not None


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
        text = _clean_text(element.get_text(" ", strip=True))
        if ':' in text:
            value = text.split(':', 1)[1].strip()
            return value or None
        return text or None

    def extract_row_value(row):
        if not row:
            return None
        tds = row.find_all('td')
        if not tds:
            return get_value_from_label(row)
        if len(tds) == 1:
            return get_value_from_label(tds[0])
        label_text = _clean_text(tds[0].get_text(" ", strip=True))
        if ':' in label_text:
            after = label_text.split(':', 1)[1].strip()
            if after:
                return after
        for td in tds[1:]:
            value = _clean_text(td.get_text(" ", strip=True))
            if value:
                return value
        return get_value_from_label(tds[0])

    # Helper to find a label and extract its associated value from the next text node
    def find_value_after_label(label_text):
        if not label_text:
            return None
        normalized_label = _normalize_text(label_text)

        label_node = soup.find(
            string=lambda t: t and normalized_label in _normalize_text(t)
        )
        if not label_node:
            return None
        label_text_value = _clean_text(label_node)
        if ':' in label_text_value:
            after = label_text_value.split(':', 1)[1].strip()
            if after:
                return after
        label_tag = label_node.parent if hasattr(label_node, 'parent') else None
        if label_tag:
            for sibling in label_tag.next_siblings:
                if isinstance(sibling, str):
                    value = _clean_text(sibling)
                else:
                    value = _clean_text(sibling.get_text(" ", strip=True))
                if value:
                    return value
        if label_tag:
            td = label_tag.find_parent('td') or label_tag
            if td:
                found_label = False
                for child in td.contents:
                    if child is label_tag or child == label_node:
                        found_label = True
                        continue
                    if not found_label:
                        continue
                    if isinstance(child, str):
                        value = _clean_text(child)
                    else:
                        value = _clean_text(child.get_text(" ", strip=True))
                    if value:
                        return value
                for next_td in td.find_next_siblings('td'):
                    value = _clean_text(next_td.get_text(" ", strip=True))
                    if value:
                        return value
        return None

    # 1. Consultation Information
    data['consultation'] = {
        'date_soins': find_value_after_label('Date des soins :'),
        'identifiant_nir': find_value_after_label('Identifiant (NIR) :')
    }

    def collect_section_rows(header_tag, stop_markers=None):
        rows = []
        if not header_tag:
            return rows
        current_tr = header_tag.find_parent('tr')
        if not current_tr:
            return rows
        for tr in current_tr.find_next_siblings('tr'):
            row_text = _normalize_text(tr.get_text(" ", strip=True))
            if stop_markers and any(marker in row_text for marker in stop_markers):
                break
            rows.append(tr)
        return rows

    def find_section_header(label: str):
        normalized_label = _normalize_text(label)
        return soup.find(
            lambda tag: tag.name in ('font', 'td', 'span', 'b', 'strong')
            and _normalize_text(tag.get_text()) == normalized_label
        )

    # 2. Ouvrant Droit (Policy Holder)
    ouvrant_droit = {"nom_famille": None, "nom_usage": None, "prenom": None}
    od_header = find_section_header("Information de l'ouvrant droit")
    od_rows = collect_section_rows(
        od_header,
        stop_markers=[
            "information du bénéficiaire",
            "information du beneficiaire",
            "information du bénéficiaire des soins",
            "information du beneficiaire des soins",
        ],
    )
    for row in od_rows:
        row_text = _normalize_text(row.get_text(" ", strip=True))
        cell = row.find('td') or row
        if "nom de famille" in row_text:
            ouvrant_droit['nom_famille'] = extract_row_value(row)
        elif "nom d'usage" in row_text or "nom d usage" in row_text:
            ouvrant_droit['nom_usage'] = extract_row_value(row)
        elif "prénom" in row_text or "prenom" in row_text:
            ouvrant_droit['prenom'] = extract_row_value(row)
    data['ouvrant_droit'] = ouvrant_droit

    # 3. Bénéficiaire (Beneficiary)
    beneficiaire = {"nom_famille": None, "prenom": None, "date_naissance": None, "rang": None}
    ben_header = find_section_header("Information du bénéficiaire des soins")
    if not ben_header:
        ben_header = find_section_header("Information du bénéficiaire")
    ben_rows = collect_section_rows(ben_header)
    for row in ben_rows:
        row_text = _normalize_text(row.get_text(" ", strip=True))
        cell = row.find('td') or row
        if "nom de famille" in row_text:
            beneficiaire['nom_famille'] = extract_row_value(row)
        elif "prénom" in row_text or "prenom" in row_text:
            beneficiaire['prenom'] = extract_row_value(row)
        elif "date de naissance/rang" in row_text or "date de naissance" in row_text:
            dob_text = extract_row_value(row)
            dob_parts = _clean_text(dob_text).split() if dob_text else []
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
    def extract_period(value: Optional[str]):
        cleaned = _clean_text(value)
        if not cleaned:
            return None, None
        match = re.search(r"\b[Dd]u\s+(\d{2}/\d{2}/\d{4}).*?\b[Aa]u\s+(\d{2}/\d{2}/\d{4})", cleaned)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def derive_status(value: Optional[str], is_active: Optional[bool], has_period: bool):
        if has_period:
            if is_active is None:
                return _clean_text(value) or None
            return "Ouverts" if is_active else "Fermés"
        if value:
            return _clean_text(value)
        if is_active is None:
            return None
        return "Ouverts" if is_active else "Fermés"

    # 5. Droits et Couvertures (Rights and Coverage)
    droits_couvertures = {}
    img_element = soup.find('img', src=lambda s: s and 'bt_vert.gif' in s)
    rights_table = img_element.find_parent('table') if img_element else None
    if not rights_table:
        rights_header = soup.find(
            string=lambda t: t and "droits" in t.lower() and "couvertures" in t.lower()
        )
        if rights_header:
            rights_table = rights_header.parent.find_parent('table')
    if rights_table:
        for row in rights_table.find_all('tr'):
            cells = row.find_all('td')
            if not cells or len(cells) < 3:
                continue

            status_img = cells[0].find('img') if cells else None
            status_src = status_img['src'] if status_img and status_img.has_attr('src') else ''

            label_text = _clean_text(cells[1].get_text(" ", strip=True))
            value_text = _clean_text(cells[2].get_text(" ", strip=True))
            is_active = 'bt_vert.gif' in status_src if status_src else None

            if "ouverture des droits" in label_text.lower():
                period_start, period_end = extract_period(value_text)
                has_period = bool(period_start and period_end)
                item = {'statut': derive_status(value_text, is_active, has_period)}
                if has_period:
                    item['periode_debut'] = period_start
                    item['periode_fin'] = period_end
                droits_couvertures['regime_base'] = item
            
            elif "exonération du ticket modérateur" in label_text.lower():
                droits_couvertures['exoneration_ticket_moderateur'] = {'statut': value_text}
            
            elif "modulation du ticket modérateur" in label_text.lower():
                droits_couvertures['modulation_ticket_moderateur'] = {'statut': value_text}
            
            elif "complémentaire santé solidaire" in label_text.lower():
                period_start, period_end = extract_period(value_text)
                has_period = bool(period_start and period_end)
                item = {'statut': derive_status(value_text, is_active, has_period)}
                if has_period:
                    item['periode_debut'] = period_start
                    item['periode_fin'] = period_end
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
        _log(f"NIR {nir} has 15 digits, truncating to first 13 digits", "yellow")
        nir_cleaned = nir_cleaned[:13]
    elif len(nir_cleaned) == 14:
        _log(f"NIR {nir} has 14 digits, using first 13", "yellow")
        nir_cleaned = nir_cleaned[:13]
    
    # Compose the eventValue string as in the curl example
    event_value = event_value_override or f"{beneficiary_name}{usual_name}{first_name}{birth_date}{nir_cleaned}"
    
    # Properly URL-encode the payload
    payload = urlencode({
        "actionTableau": "selectpuceimg###eventValue",
        "eventValue": event_value
    })
    
    _log(f"Alternative fetch - Beneficiary: {beneficiary_name}, Event value base: {event_value}", "cyan")

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
        _log(f"Timeout or error in alternative fetch: {str(e)}", "red")
        return None
    
    if isinstance(response, str) and response.startswith('Error'):
        _log(f"Error in alternative fetch: {response}", "red")
        return None
    
    _log(f"Alternative fetch successful - received {len(response) if response else 0} bytes", "green")
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
        _log(json_output)

    except FileNotFoundError:
        _log("Error: 'data.html' not found. Make sure the file is in the same directory as the script.")
    except Exception as e:
        _log(f"An error occurred: {e}")
