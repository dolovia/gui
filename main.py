import json
from bs4 import BeautifulSoup
from collections import deque
from queue import Queue
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from threading import Thread, Event
from typing import Optional, Callable
from time import sleep, time
from datetime import datetime
from utils import parse_rights_data, alterative_fetch_post, set_logger
import pandas as pd
from termcolor import colored
from config import WORKING_PORT, WORKER_NAME, BATCH_SIZE, SLEEP_PER_REQUEST, SLEEP_PER_BATCH
import subprocess
import os
import signal
import platform
import shutil


@dataclass
class RunConfig:
    working_port: int = WORKING_PORT
    worker_name: str = WORKER_NAME
    batch_size: int = BATCH_SIZE
    sleep_per_request: int = SLEEP_PER_REQUEST
    sleep_per_batch: int = SLEEP_PER_BATCH
    names_file: str = "names.txt"
    results_file: str = "results.xlsx"
    pause_on_finish: int = 30


def make_logger(
    logger: Optional[Callable[[str], None]] = None,
    use_color: bool = True
) -> Callable[[str, Optional[str]], None]:
    def _log(message: str, color: Optional[str] = None) -> None:
        text = colored(message, color) if use_color and color else message
        (logger or print)(text)
    return _log


def parse_html_to_dict(html):
    # kept for backward compatibility; prefer parse_rights_data from utils
    return parse_rights_data(html)


def normalize_nni(value):
    if value is None:
        return ''
    digits = ''.join(ch for ch in str(value) if ch.isdigit())
    if len(digits) >= 13:
        return digits[:13]
    return digits


def resolve_default_datesoins(driver):
    try:
        element = driver.find_element(By.ID, "idsoins")
        value = element.get_attribute("value") or ""
        if value.strip():
            return value.strip()
    except Exception:
        pass
    return datetime.now().strftime("%d%m%Y")


def connect_driver(working_port: int):
    options = Options()
    options.debugger_address = f"127.0.0.1:{working_port}"
    return webdriver.Chrome(options=options)


def connect_or_start_driver(working_port: int, log: Callable[[str, Optional[str]], None]):
    try:
        return connect_driver(working_port)
    except Exception:
        log("No existing Chrome debug session found. Starting one...", "yellow")
        start_chrome_debug(working_port, log)
        return connect_driver(working_port)


def fetch_post_by_name(
    driver,
    nom='',
    prenom='',
    datesoins=None,
    nni=None,
    naissance='',
    log: Optional[Callable[[str, Optional[str]], None]] = None
):
    """Send a POST by nom/prenom (last name / first name) and return parsed data/status.

    Returns: (data_list or None, status_string)
    status_string: 'success' (one or more candidates found), 'not_found', 'insurance_issue'
    When successful, returns a list of dicts with all successfully scraped candidates.
    """
    nni_clean = normalize_nni(nni)
    if nni_clean:
        nom = ''
        prenom = ''

    identifier = nni_clean or f"{nom} {prenom}".strip()

    if datesoins is None:
        datesoins = ''

    js_code = """
        var cb = arguments[arguments.length - 1];
        var nomArg = arguments[0] || '';
        var prenomArg = arguments[1] || '';
        var datesoinsArg = arguments[2] || '';
        var nniArg = arguments[3] || '';
        var naissanceArg = arguments[4] || '';

        try {
            var url = 'https://portail.sesam-vitale.fr/cdr/amo/CNAM/PQ_J/Consultation.do';
            var isHttps = window.location.href.toString().substring(0,5) === 'https';
            function setcookie(name, value) {
                document.cookie = name + '=' + value + '; path=/' + (isHttps ? '; secure' : '');
            }
            if (nniArg) { setcookie('NIR', nniArg); }
            if (nomArg !== null) { setcookie('NOM', nomArg); }
            if (prenomArg !== null) { setcookie('PRENOM', prenomArg); }
            if (naissanceArg !== null) { setcookie('DATE_NAIS', naissanceArg); }
            if (datesoinsArg !== null) { setcookie('DATE_SOINS', datesoinsArg); }
            var form = new URLSearchParams({
                nni: nniArg,
                nom: nomArg,
                datesoins: datesoinsArg,
                prenom: prenomArg,
                naissance: naissanceArg
            });

            fetch(url, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'fr-FR,fr;q=0.9'
                },
                body: form.toString(),
                mode: 'same-origin'
            }).then(function(resp) {
                if (!resp.ok) {
                    return resp.text().then(function(errText) {
                        throw new Error('Request failed: ' + resp.status + ' ' + resp.statusText);
                    });
                }
                return resp.text();
            }).then(function(html) {
                cb(html);
            }).catch(function(err) {
                cb('Error: ' + err.message);
            });
        } catch (err) {
            cb('Error: ' + err.message);
        }
            """

    if log is None:
        log = make_logger()

    response = driver.execute_async_script(js_code, nom, prenom, datesoins, nni_clean, naissance)
    if isinstance(response, str) and response.startswith('Error'):
        log(f"Error for {identifier}: {response}", "red")
        return None, 'error'

    try:
        data = parse_rights_data(response)
    except Exception:
        data = None

    if data is not None:
        log(f"Successfully fetched data for {identifier}", "green")
        return [data], 'success'

    # try to detect a candidate list and fetch alternative
    try:
        candidates = parse_all_candidate_rows(response)
        log(f" Found {len(candidates)} candidates for {identifier}", "yellow")
    except Exception:
        candidates = []
    
    if candidates:
        log(f" {len(candidates)} users found for {identifier} Extracting each...", "yellow")
        successful_candidates = []
        
        # Loop through each candidate and scrape ALL of them
        for idx, candidate in enumerate(candidates, 1):
            log(
                f"  [{idx}/{len(candidates)}] Scraping: {candidate['Nom du bénéficiaire']} {candidate['Prénom']} (DOB: {candidate['Date de naissance']}, NIR: {candidate['NIR']})",
                "cyan"
            )
            
            teg = alterative_fetch_post(
                driver,
                candidate['Nom du bénéficiaire'],
                candidate['Nom usage'],
                candidate['Prénom'],
                candidate['Date de naissance'],
                candidate['NIR'],
                candidate.get('event_value')
            )
            
            try:
                data = parse_rights_data(teg)
                if data is not None:
                    log(f"  ✓ Successfully scraped candidate {idx}: {candidate['Nom du bénéficiaire']} {candidate['Prénom']}", "green")
                    successful_candidates.append(data)
                else:
                    log(f"  ✗ Candidate {idx} returned empty data", "yellow")
            except Exception:
                log(
                    f"failed and skipping  {candidate['Nom du bénéficiaire']} {candidate['Prénom']} (DOB: {candidate['Date de naissance']}, NIR: {candidate['NIR']})",
                    "red"
                )
                # save only the NIR number (digits only) to failed/failed_candidates.txt
                import os
                os.makedirs('failed', exist_ok=True)
                nir_raw = candidate.get('NIR', '')
                nir_digits = ''.join(ch for ch in str(nir_raw) if ch.isdigit())
                if nir_digits:
                    failed_nir = nir_digits
                else:
                    failed_nir = str(nir_raw).strip()
                with open('failed/failed_candidates.txt', 'a') as f:
                    f.write(f"{failed_nir}\n")
                continue
        
        # Return all successful candidates or insurance_issue if none succeeded
        if successful_candidates:
            log(f"✓ Successfully scraped {len(successful_candidates)} out of {len(candidates)} candidates", "green")
            return successful_candidates, 'success'
        else:
            log(f"All {len(candidates)} candidates failed to parse", "red")
            return None, 'insurance_issue'
    else:
        log(f"No user found for {identifier}", "red")
        return None, 'not_found'


def parse_all_candidate_rows(html):
    """Parse ALL candidate rows from the alternative data list, not just the first one."""
    soup = BeautifulSoup(html, 'html.parser')
    candidates = []
    
    # find the header row that contains "Nom du bénéficiaire"
    header_row = None
    for tr in soup.find_all('tr'):
        if 'Nom du bénéficiaire' in tr.get_text(" ", strip=True):
            header_row = tr
            break
    if not header_row:
        return candidates
    
    # find ALL data rows after the header with class lignePaire/ligneImpaire
    def is_data_row(tag):
        if tag.name != 'tr':
            return False
        classes = tag.get('class') or []
        return any(c in ('lignePaire', 'ligneImpaire') for c in classes)

    rows = header_row.find_all_next(is_data_row)
    for row in rows:
        tds = row.find_all('td')
        if len(tds) < 5:
            continue

        event_value = None
        link = row.find('a', href=True)
        if link and 'selectLineByKey' in link.get('href', ''):
            href = link.get('href', '')
            parts = href.split(',')
            if len(parts) >= 2 and "'" in parts[1]:
                event_value = parts[1].split("'")[1]
        if not event_value and link and link.get('id'):
            link_id = link.get('id', '')
            if '###' in link_id:
                event_value = link_id.split('###')[-1]

        candidate = {
            'Nom du bénéficiaire': tds[0].get_text(strip=True),
            'Nom usage': tds[1].get_text(strip=True),
            'Prénom': tds[2].get_text(strip=True),
            'Date de naissance': tds[3].get_text(strip=True),
            'NIR': tds[4].get_text(strip=True),
            'event_value': event_value
        }
        candidates.append(candidate)
    
    return candidates


def parse_first_candidate_row(html):
    """Backward compatible wrapper - returns first candidate only."""
    candidates = parse_all_candidate_rows(html)
    return candidates[0] if candidates else None


def kill_chrome_processes():
    """Kill Chrome processes started for the debug session."""
    try:
        system = platform.system().lower()
        if system == 'windows':
            subprocess.run(
                ['taskkill', '/IM', 'chrome.exe', '/F'],
                capture_output=True,
                timeout=5
            )
        elif system == 'linux':
            chrome_names = [
                'google-chrome',
                'google-chrome-stable',
                'chromium',
                'chromium-browser',
                'chrome',
            ]
            for chrome_name in chrome_names:
                subprocess.run(
                    ['pkill', '-f', chrome_name],
                    capture_output=True,
                    timeout=5
                )
        else:
            print(colored(f"Chrome cleanup is not configured for {system}", "yellow"))
        print(colored("Killed existing Chrome processes", "yellow"))
    except Exception as e:
        print(colored(f"Could not kill Chrome processes: {e}", "yellow"))
    sleep(2)  # Give time for processes to fully terminate


def get_chrome_command():
    """Return the Chrome/Chromium executable command for the current OS."""
    env_chrome_path = os.environ.get("CHROME_PATH")
    if env_chrome_path:
        return [env_chrome_path]

    system = platform.system().lower()
    if system == 'windows':
        return [r"C:\Program Files\Google\Chrome\Application\chrome.exe"]

    if system == 'linux':
        candidates = [
            'google-chrome',
            'google-chrome-stable',
            'chromium',
            'chromium-browser',
            'chrome',
        ]
        for candidate in candidates:
            chrome_path = shutil.which(candidate)
            if chrome_path:
                return [chrome_path]
        raise FileNotFoundError(
            "Chrome/Chromium was not found. Install it or set CHROME_PATH."
        )

    raise OSError(f"Unsupported operating system: {system}")


def get_user_data_dir():
    system = platform.system().lower()
    if system == 'windows':
        return r"C:\chrome_debug"
    if system == 'linux':
        return os.path.join('/tmp', 'chrome_debug')
    raise OSError(f"Unsupported operating system: {system}")


def start_chrome_debug(working_port: int, log: Callable[[str, Optional[str]], None]):
    """Start Chrome in debug mode on the specified port"""
    chrome_command = get_chrome_command()
    user_data_dir = get_user_data_dir()
    
    # Create user data directory if it doesn't exist
    os.makedirs(user_data_dir, exist_ok=True)
    
    try:
        log(f"Starting Chrome in debug mode on port {working_port}...", "cyan")
        subprocess.Popen(
            chrome_command + [
                f'--remote-debugging-port={working_port}',
                f'--user-data-dir={user_data_dir}'
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        log("Chrome started successfully", "green")
        sleep(3)  # Wait for Chrome to fully start
    except FileNotFoundError:
        log("Error: Chrome/Chromium executable was not found", "red")
        raise
    except Exception as e:
        log(f"Error starting Chrome: {e}", "red")
        raise


def flatten_dict(data, parent_key='', sep='_'):
    """Flatten nested dictionary for Excel export"""
    items = []
    for k, v in data.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _write_remaining_nnis(file_path, remaining):
    remaining_list = list(remaining)
    with open(file_path, 'w', encoding='utf-8') as fh:
        if remaining_list:
            fh.write('\n'.join(remaining_list) + '\n')
        else:
            fh.write('')


def start_cleanup_worker(initial_nnis, file_path, flush_every=25):
    remaining = deque(initial_nnis)
    queue = Queue()

    def worker():
        pending_flush = 0
        while True:
            item = queue.get()
            if item is None:
                break
            removed = False
            if remaining:
                if remaining[0] == item:
                    remaining.popleft()
                    removed = True
                else:
                    try:
                        remaining.remove(item)
                        removed = True
                    except ValueError:
                        pass
            if removed:
                pending_flush += 1
                if pending_flush >= flush_every:
                    _write_remaining_nnis(file_path, remaining)
                    pending_flush = 0
        _write_remaining_nnis(file_path, remaining)

    thread = Thread(target=worker, name='SNNFileCleanupThread', daemon=False)
    thread.start()
    return queue, thread


def run_job(
    config: Optional[RunConfig] = None,
    logger: Optional[Callable[[str], None]] = None,
    use_color: bool = True,
    progress_cb: Optional[Callable[[dict], None]] = None,
    stop_event: Optional[Event] = None
):
    if config is None:
        config = RunConfig()

    log = make_logger(logger, use_color)
    set_logger(logger, use_color)
    start_time = time()

    file_path = config.names_file
    save_file_name = config.results_file
    processed_count = 0
    total_lines = 0
    results = []
    not_found_list = []
    insurance_issue_list = []
    request_error_list = []
    stop_requested = False

    def build_summary(status: str, message: Optional[str] = None) -> dict:
        end_time = time()
        elapsed_time = end_time - start_time
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)
        return {
            "status": status,
            "message": message or "",
            "processed": processed_count,
            "total": total_lines,
            "success": len(results),
            "not_found": len(not_found_list),
            "insurance_issue": len(insurance_issue_list),
            "request_error": len(request_error_list),
            "elapsed_seconds": int(elapsed_time),
            "elapsed_hms": f"{hours}h {minutes}m {seconds}s",
            "results_file": save_file_name,
            "names_file": file_path,
            "stopped": stop_requested
        }
    
    driver = connect_or_start_driver(config.working_port, log)
    driver.get("https://portail.sesam-vitale.fr/cdr/amo/CNAM/PQ_J/accueilPQ.do")
    try:
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "idsoins")))
    except TimeoutException:
        log("Timed out waiting for the consultation form. Check login/session.", "red")
        return build_summary("error", "Timed out waiting for the consultation form.")

    default_datesoins = resolve_default_datesoins(driver)
    
    # Use default file names
    log(f"Using names file: {file_path}", "cyan")
    log(f"Results will be saved to: {save_file_name}", "cyan")
    log("Make sure the portal page is accessible in this Chrome session.", "green")
    log(f"Processing started...using {config.worker_name}", "green")
    sleep(2)  # brief pause before starting
    # load existing results.xlsx (if any)
    try:
        df = pd.read_excel(save_file_name, engine='openpyxl')
        results = df.to_dict('records')
    except (FileNotFoundError, Exception):
        log("No existing results found, starting fresh.", "yellow")
        results = []

    # Load all names from text file into memory at once (OPTIMIZATION: avoid repeated file reads)
    names_list = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:  # Skip empty lines
                    if line.isdigit() and len(line) >= 13:
                        names_list.append({'nni': line})
                    else:
                        parts = line.split(maxsplit=1)  # Split on first whitespace
                        if len(parts) == 2:
                            names_list.append({'nom': parts[0], 'prenom': parts[1]})
                        elif len(parts) == 1:
                            names_list.append({'nom': parts[0], 'prenom': ''})
    except FileNotFoundError:
        log(f"Error: File '{file_path}' not found.", "red")
        driver.quit()
        return build_summary("error", f"Names file '{file_path}' not found.")

    total_lines = len(names_list)
    log(f"Total names to process: {total_lines}", "cyan")

    # Build a list of string keys for cleanup ("NOM PRENOM")
    initial_keys = []
    for r in names_list:
        try:
            nni = str(r.get('nni', '')).strip()
        except Exception:
            nni = ''
        try:
            n = str(r.get('nom', '')).strip()
        except Exception:
            n = ''
        try:
            p = str(r.get('prenom', '')).strip()
        except Exception:
            p = ''
        key = nni if nni else f"{n} {p}".strip()
        initial_keys.append(key)

    cleanup_queue = None
    cleanup_thread = None
    if initial_keys:
        cleanup_queue, cleanup_thread = start_cleanup_worker(initial_keys, "names_remaining.txt")

    batch_counter = 0

    def emit_progress(current: Optional[str] = None) -> None:
        if progress_cb:
            progress_cb({
                "processed": processed_count,
                "total": total_lines,
                "success": len(results),
                "not_found": len(not_found_list),
                "insurance_issue": len(insurance_issue_list),
                "request_error": len(request_error_list),
                "current": current
            })

    emit_progress()

    # Process names from loaded list
    for name in names_list:
        if stop_event is not None and stop_event.is_set():
            stop_requested = True
            log("Stop requested. Finishing up current work...", "yellow")
            break
        nni = str(name.get('nni', '')).strip()
        nom = str(name.get('nom', '')).strip()
        prenom = str(name.get('prenom', '')).strip()
        search_key = nni if nni else f"{nom} {prenom}".strip()
        processed_count += 1
        try:
            result_list, status = fetch_post_by_name(
                driver,
                nom=nom,
                prenom=prenom,
                datesoins=default_datesoins,
                nni=nni,
                log=log
            )
            if status == 'success' and result_list:
                # result_list is now a list of dicts (all successful candidates)
                for idx, result in enumerate(result_list, 1):
                    # Flatten nested structure for Excel
                    flat_result = flatten_dict(result)
                    # include the searched name for traceability
                    if nni:
                        flat_result['search_nni'] = nni
                    else:
                        flat_result['search_nom'] = nom
                        flat_result['search_prenom'] = prenom
                    flat_result['candidate_num'] = idx  # Track which candidate number this is
                    results.append(flat_result)
                    batch_counter += 1
                    log(f"  Added candidate {idx} to results", "green")
            elif status == 'not_found':
                not_found_list.append(search_key)
            elif status == 'insurance_issue':
                insurance_issue_list.append(search_key)
            elif status == 'error':
                request_error_list.append(search_key)

            # Save to Excel every BATCH_SIZE records (configurable)
            if batch_counter >= config.batch_size:
                df = pd.DataFrame(results)
                df.to_excel(save_file_name, index=False, engine='openpyxl')
                log(f"Batch saved: {len(results)} total records", "green")
                batch_counter = 0
                if config.sleep_per_batch > 0:
                    sleep(config.sleep_per_batch)

            log(f"Processed name: {search_key} [{processed_count}/{total_lines}]", "cyan")
        finally:
            if cleanup_queue is not None:
                cleanup_queue.put(search_key)
        emit_progress(search_key)
        if config.sleep_per_request > 0:
            sleep(config.sleep_per_request)

    # Write all not-found records at once (OPTIMIZATION: batch write)
    if not_found_list:
        with open("not_found.txt", "a", encoding="utf-8") as nf:
            nf.writelines([f"{name}\n" for name in not_found_list])

    # Write all insurance issue records at once
    if insurance_issue_list:
        with open("insurance_issue.txt", "a", encoding="utf-8") as ii:
            ii.writelines([f"{name}\n" for name in insurance_issue_list])
    if request_error_list:
        with open("request_errors.txt", "a", encoding="utf-8") as re:
            re.writelines([f"{name}\n" for name in request_error_list])

    # save any remaining results to results.xlsx
    if results:
        df = pd.DataFrame(results)
        df.to_excel(save_file_name, index=False, engine='openpyxl')
        log(f"Final save: {len(results)} total records", "green")

    if cleanup_queue is not None:
        cleanup_queue.put(None)
        cleanup_thread.join()

    end_time = time()
    elapsed_time = end_time - start_time
    hours = int(elapsed_time // 3600)
    minutes = int((elapsed_time % 3600) // 60)
    seconds = int(elapsed_time % 60)

    if stop_requested:
        log("Processing stopped early. Partial results have been saved.", "yellow")

    emit_progress()
    log("="*50, "green")
    log(f"Total processed: {processed_count}/{total_lines}", "green")
    log(f"Successful: {len(results)}", "green")
    log(f"Not found: {len(not_found_list)}", "yellow")
    log(f"Insurance issues: {len(insurance_issue_list)}", "red")
    log(f"Request errors: {len(request_error_list)}", "red")
    log(f"Time taken: {hours}h {minutes}m {seconds}s", "cyan")
    log("="*50, "green")
    log("Results saved to Excel.")
    if config.pause_on_finish > 0:
        log(f"quitting in {config.pause_on_finish} seconds...")
        sleep(config.pause_on_finish)
    #driver.quit()
    status = "stopped" if stop_requested else "success"
    return build_summary(status)


if __name__ == "__main__":
    run_job()
