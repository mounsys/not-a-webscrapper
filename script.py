import os
import re
import json
import time
import requests
import logging
from urllib.parse import urlparse, urljoin, quote, parse_qs
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from concurrent.futures import ThreadPoolExecutor, as_completed
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By

class APIScanner:
    def __init__(self):
        self.config_file = os.path.join("config", "config.json")
        self.default_config = {
            'target_url': None,
            'browser': 'chrome',
            'headless': True,
            'proxy': None,
            'depth': 2,
            'workers': 10,
            'delay': 1.0,
            'timeout': 15
        }
        self.config = self._load_config()
        self.session = None
        self.driver = None
        self.found_apis = {}
        self._setup_logging()
        
    def _load_config(self):
        """Carga la configuración desde el archivo o usa valores por defecto"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            return self.default_config.copy()
        except Exception as e:
            print(f"Error cargando configuración: {str(e)}")
            return self.default_config.copy()

    def _save_config(self):
        """Guarda la configuración actual en el archivo"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error guardando configuración: {str(e)}")

    def _setup_logging(self):
        self.logger = logging.getLogger("APIScanner")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        log_dir = os.path.join("results", "logs")
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(
            os.path.join(log_dir, f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def show_menu(self):
        self._print_banner()
        while True:
            print("\n[1] Configurar objetivo")
            print("[2] Configurar navegador")
            print("[3] Configurar proxy")
            print("[4] Configurar parámetros avanzados")
            print("[5] Iniciar escaneo")
            print("[6] Salir")
            
            choice = input("\nSeleccione una opción: ")
            
            if choice == '1':
                self._set_target()
            elif choice == '2':
                self._set_browser()
            elif choice == '3':
                self._set_proxy()
            elif choice == '4':
                self._set_advanced()
            elif choice == '5':
                self.run_scan()
            elif choice == '6':
                print("\n¡nv!")
                break
            else:
                print("❌ Opción inválida")

    def _set_target(self):
        url = input("\nIngrese la URL objetivo (ej: https://ejemplo.com): ").strip()
        if url.startswith(('http://', 'https://')):
            self.config['target_url'] = url
            print("✅ URL objetivo configurada")
            self._save_config()
        else:
            print("❌ La URL debe incluir http:// o https://")
        time.sleep(1)

    def _set_browser(self):
        print("\nNavegadores disponibles:")
        print("1. Chrome (predeterminado)")
        print("2. Firefox")
        print("3. Edge")
        choice = input("Seleccione navegador: ").strip()
        
        browsers = {'1': 'chrome', '2': 'firefox', '3': 'edge'}
        self.config['browser'] = browsers.get(choice, 'chrome')
        print(f"✅ Navegador configurado: {self.config['browser'].title()}")
        self._save_config()
        time.sleep(1)

    def _set_proxy(self):
        proxy = input("\nIngrese proxy (ej: http://127.0.0.1:8080): ").strip()
        if proxy:
            try:
                parsed = urlparse(proxy)
                if parsed.scheme and parsed.netloc:
                    self.config['proxy'] = proxy
                    print("✅ Proxy configurado")
                else:
                    print("❌ Formato de proxy inválido")
            except:
                print("❌ Error al procesar proxy")
        else:
            self.config['proxy'] = None
            print("✅ Proxy desactivado")
        self._save_config()
        time.sleep(1)

    def _set_advanced(self):
        print("\nConfiguración avanzada:")
        try:
            self.config['depth'] = int(input(f"Profundidad de análisis [1-5] (actual: {self.config['depth']}): ") or 2)
            self.config['workers'] = int(input(f"Hilos paralelos [1-20] (actual: {self.config['workers']}): ") or 10)
            self.config['delay'] = float(input(f"Delay entre peticiones [0.5-5] (actual: {self.config['delay']}): ") or 1.0)
            self.config['timeout'] = int(input(f"Timeout peticiones [5-30] (actual: {self.config['timeout']}): ") or 15)
            print("✅ Configuración avanzada actualizada")
            self._save_config()
        except ValueError:
            print("❌ Valores inválidos")
        time.sleep(1)

    def _get_browser_options(self):
        """Devuelve las opciones del navegador según la configuración"""
        browser = self.config['browser']
        if browser == 'firefox':
            options = FirefoxOptions()
            options.set_preference('devtools.jsonview.enabled', False)
            options.set_preference('devtools.netmonitor.enabled', True)
        elif browser == 'edge':
            options = EdgeOptions()
            options.use_chromium = True
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        else:  # Chrome
            options = ChromeOptions()
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0")

        if self.config['headless']:
            options.add_argument("--headless=new")

        if browser == 'edge':
            options.add_argument("--disable-features=NetworkService")
            options.add_argument("--force-device-scale-factor=1")

        if self.config['proxy']:
            if browser == 'firefox':
                proxy = urlparse(self.config['proxy'])
                options.set_preference('network.proxy.http', proxy.hostname)
                options.set_preference('network.proxy.http_port', proxy.port or 8080)
            else:
                options.add_argument(f"--proxy-server={self.config['proxy']}")

        return options
    def _init_session(self):
        self.session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json, */*',
            'Accept-Encoding': 'gzip, deflate'
        }
        self.session.headers.update(headers)
        
        if self.config['proxy']:
            self.session.proxies = {
                'http': self.config['proxy'],
                'https': self.config['proxy']
            }

    def _init_browser(self):
        try:
            options = self._get_browser_options()
            browser = self.config['browser']
            
            if browser == 'firefox':
                self.driver = webdriver.Firefox(
                    service=FirefoxService(GeckoDriverManager().install()),
                    options=options
                )
            elif browser == 'edge':
                options.add_argument("--enable-chrome-logs")
                self.driver = webdriver.Edge(
                    service=EdgeService(EdgeChromiumDriverManager().install()),
                    options=options
                )
            else:
                self.driver = webdriver.Chrome(
                    service=ChromeService(ChromeDriverManager().install()),
                    options=options
                )
            
            self.driver.set_page_load_timeout(self.config['timeout'])
            self.driver.implicitly_wait(10)
            return True
        except Exception as e:
            self.logger.error(f"Error inicializando navegador: {str(e)}")
            return False

    def _analyze_static(self, url):
        self.logger.info("Analizando contenido estático avanzado...")
        found = set()
        
        try:
            response = self.session.get(url, timeout=self.config['timeout'])
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Detección de endpoints en atributos HTML
            for tag in soup.find_all(['a', 'link', 'script', 'form', 'img', 'iframe']):
                attrs = ['href', 'src', 'action', 'data-src', 'data-url']
                for attr in attrs:
                    if tag.has_attr(attr):
                        found.add(urljoin(url, tag[attr]))
    
            # Análisis profundo de scripts JavaScript
            for script in soup.find_all('script'):
                content = script.string or ''
                found.update(self._find_js_endpoints(content, url))
                found.update(self._find_graphql_endpoints(content, url))
                found.update(self._find_websockets(content, url))
    
            # Detección de API Docs (OpenAPI/Swagger)
            doc_paths = ['/swagger.json', '/openapi.yaml', '/api-docs', '/redoc']
            found.update(urljoin(url, path) for path in doc_paths)
    
            return list(found)
        except Exception as e:
            self.logger.error(f"Error análisis estático: {str(e)}")
            return []
    
    def _find_graphql_endpoints(self, content, base_url):
        endpoints = set()
        patterns = [
            r'fetch\(["\'](.*?graphql)["\']',
            r'\.post\(["\'](.*?graphql)["\']',
            r'const\s+GRAPHQL_ENDPOINT\s*=\s*["\'](.*?)["\']'
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                endpoints.add(urljoin(base_url, match.group(1)))
        return endpoints
    
    def _find_websockets(self, content, base_url):
        endpoints = set()
        pattern = r'new\s+WebSocket\(["\'](wss?://.*?)["\']'
        for match in re.finditer(pattern, content, re.IGNORECASE):
            endpoints.add(match.group(1))
        return endpoints

    def _find_js_endpoints(self, content, base_url):
        patterns = [
            r'(fetch|axios|XMLHttpRequest)\(["\']([^"\']+)["\']',
            r'\.get(?:JSON)?\(["\']([^"\']+)["\']',
            r'api(?:Key|Url|Endpoint)\s*=\s*["\']([^"\']+)["\']'
        ]
        endpoints = set()
        
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                endpoint = match.group(2) if 'fetch' in match.group(0) else match.group(1)
                endpoints.add(urljoin(base_url, endpoint))
                
        return endpoints

    def _capture_network(self):
        self.logger.info("Capturando tráfico de red...")
        requests = []

        if not self.driver:
            self.logger.warning("Navegador no inicializado")
            return requests

        try:
            if self.config['browser'] == 'firefox':
                self.logger.info("Firefox no soporta captura de tráfico mediante performance logs. Omitiendo...")
                return []
            available_logs = self.driver.log_types
            if 'performance' not in available_logs:
                self.logger.warning("Los logs de performance no están disponibles")
                return []

            try:
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.TAG_NAME, 'body'))
                )
            except TimeoutException:
                self.logger.warning("Tiempo de espera excedido para carga del cuerpo")

            logs = []
            for attempt in range(3):
                try:
                    logs = self.driver.get_log('performance')
                    if logs:
                        break
                    self.logger.info("Intento %d: No se encontraron logs", attempt+1)
                except Exception as e:
                    self.logger.warning("Error obteniendo logs: %s", str(e))
                time.sleep(2)
            unique_urls = set()
            for entry in logs:
                try:
                    message = json.loads(entry['message'])['message']
                    if message['method'] == 'Network.requestWillBeSent':
                        request = message['params']['request']
                        url = request.get('url', '')
                        if url.startswith(('http', 'https')):
                            parsed_url = urlparse(url)
                            clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                            unique_urls.add(clean_url)
                except Exception as e:
                    continue
            for entry in logs:
                try:
                    message = json.loads(entry['message'])['message']
                    method = message['method']

                    # Capturar diferentes tipos de solicitudes
                    if method in ['Network.requestWillBeSent', 'Network.webSocketCreated']:
                        request = message['params'].get('request') or message['params']
                        url = request.get('url', '')

                        # Filtrar y normalizar URLs
                        if self._is_api_url(url):
                            parsed = urlparse(url)
                            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                            unique_urls.add(clean_url)

                except Exception as e:
                    continue

            return list(unique_urls)[:500]

        except Exception as e:
            self.logger.error("Error en captura de red: %s", str(e), exc_info=True)
            return []
        
    def _is_api_url(self, url):
        api_indicators = [
            '/api', '/graphql', '/rest', 
            '/v1', '/v2', '/json', '/xml',
            'action=', 'endpoint=', 'callback='
        ]
        return any(indicator in url.lower() for indicator in api_indicators)
        
    def _fuzz_endpoints(self, base_url):
        self.logger.info("Generando endpoints para fuzzing avanzado...")
        domain = urlparse(base_url).netloc.split('.')[-2]  # Extraer dominio principal

        endpoints = [
            f'/api/{domain}', f'/v1/{domain}', 
            '/graphql', '/rest', '/oauth2',
            '/users', '/products', '/data',
            '/admin', '/internal', '/private',
            '/search', '/query', '/mutations'
        ]

        # Generar variantes con parámetros
        param_variants = [
            '?id=1', '?page=1', 
            '?format=json', '?api_key=TEST'
        ]

        return [urljoin(base_url, ep + pv) for ep in endpoints for pv in param_variants]

    def _validate_api(self, url):
        try:
            # Filtrar recursos estáticos
            if re.search(r'\.(js|css|png|jpe?g|gif|svg|ico|woff2?)(\?|$)', url, re.I):
                return False

            response = self.session.get(url, timeout=self.config['timeout'])

            # Detectar por headers
            api_headers = ['x-api-version', 'x-rate-limit', 'content-location']
            if any(h in response.headers for h in api_headers):
                return True

            # Analizar estructura de respuesta
            content = response.text[:1000].lower()
            json_like = re.search(r'^{\s*".+?":', content)
            xml_like = re.search(r'^<\?xml|<\/\w+>', content)

            # Detectar patrones comunes
            api_patterns = [
                'error', 'message', 'status', 
                'results', 'data', 'total'
            ]

            return any([
                'json' in response.headers.get('Content-Type', ''),
                'xml' in response.headers.get('Content-Type', ''),
                response.status_code in (200, 201, 400, 401, 403),
                json_like or xml_like,
                any(p in content for p in api_patterns)
            ])

        except Exception as e:
            return False

    def _analyze_endpoint(self, url):
        analysis = {
            'methods': {},
            'parameters': {},
            'security': {},
            'vulnerabilities': []
        }

        for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.config['timeout'],
                    json={'test': 'payload'} if method in ['POST', 'PUT'] else None
                )

                analysis['methods'][method] = {
                    'status': response.status_code,
                    'headers': dict(response.headers),
                    'size': len(response.content),
                    'data_sample': response.text[:500] if response.text else None
                }

                # Detectar vulnerabilidades básicas
                if method == 'GET' and response.status_code == 200:
                    if 'sql' in response.text.lower():
                        analysis['vulnerabilities'].append('Possible SQLi')

                if method == 'POST' and response.status_code == 200:
                    if 'test' in response.text:
                        analysis['vulnerabilities'].append('Possible Unfiltered Input')

            except Exception as e:
                analysis['methods'][method] = {'error': str(e)}

        parsed = urlparse(url)
        analysis['parameters'] = parse_qs(parsed.query)

        # Verificar autenticación
        test_url = urljoin(url, '/../')
        response = self.session.get(test_url)
        if response.status_code < 400:
            analysis['security']['directory_traversal'] = True

        return analysis

    def _generate_report(self):
        report = {
            'config': self.config,
            'timestamp': datetime.now().isoformat(),
            'endpoints': {},
            'stats': {
                'total': 0,
                'vulnerable': 0,
                'average_params': 0
            }
        }
        
        for url, data in self.found_apis.items():
            report['endpoints'][url] = data
            report['stats']['total'] += 1
            if data.get('vulnerabilities'):
                report['stats']['vulnerable'] += 1
        
        report_dir = os.path.join("results", "reports")
        os.makedirs(report_dir, exist_ok=True)
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(os.path.join(report_dir, filename), 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\n✅ Reporte generado: {os.path.join(report_dir, filename)}")

    def run_scan(self):
        if not self.config['target_url']:
            print("❌ Primero configure una URL objetivo")
            return

        try:
            self._init_session()
            if not self._init_browser():
                return

            print("\n🚀 Iniciando escaneo completo...")

            # Inicializar todas las variables
            static_urls = []
            dynamic_urls = []
            fuzzed_urls = []

            try:
                static_urls = self._analyze_static(self.config['target_url'])
            except Exception as e:
                self.logger.error(f"Error en análisis estático: {str(e)}")

            try:
                # Configurar tiempo de espera
                dynamic_timeout = self.config['timeout'] * 2
                self.driver.set_page_load_timeout(dynamic_timeout)
                self.driver.get(self.config['target_url'])
                
                WebDriverWait(self.driver, dynamic_timeout).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete' 
                    or d.find_elements(By.TAG_NAME, 'body')
                )

            except TimeoutException:
                self.logger.warning("Timeout de navegación principal")
                try:
                    self.driver.execute_script("window.stop()")
                except Exception as e:
                    self.logger.warning(f"Error deteniendo carga: {str(e)}")
            except WebDriverException as e:
                self.logger.error(f"Error de navegador: {str(e)}")
            finally:
                # Capturar tráfico siempre
                try:
                    dynamic_urls = self._capture_network()
                except Exception as e:
                    self.logger.error(f"Error capturando tráfico: {str(e)}")
                    dynamic_urls = []

            try:
                fuzzed_urls = self._fuzz_endpoints(self.config['target_url'])
            except Exception as e:
                self.logger.error(f"Error generando endpoints: {str(e)}")
                fuzzed_urls = []

            # Combinación segura de URLs
            all_urls = set()
            all_urls.update(static_urls)
            all_urls.update(dynamic_urls)
            all_urls.update(fuzzed_urls)

            print(f"\n🔍 Encontrados {len(all_urls)} candidatos potenciales")

            with ThreadPoolExecutor(max_workers=self.config['workers']) as executor:
                futures = {executor.submit(self._validate_api, url): url for url in all_urls}

                for future in as_completed(futures):
                    url = futures[future]
                    try:
                        if future.result():
                            analysis = self._analyze_endpoint(url)
                            self.found_apis[url] = analysis
                            print(f"✅ API válida encontrada: {url}")
                    except Exception as e:
                        self.logger.warning(f"Error validando {url}: {str(e)}")

            self._generate_report()

        except Exception as e:
            self.logger.error(f"Error crítico: {str(e)}", exc_info=True)
        finally:
            if self.driver:
                self.driver.quit()

    def _print_banner(self):
        print(r"""
▓█████▄  ▓█████▄  ██▒   █▓ ███▄ ▄███▓
▒██▀ ██▌▒██▀ ██▌▓██░   █▒▓██▒▀█▀ ██▒
░██   █▌░██   █▌ ▓██  █▒░▓██    ▓██░
░▓█▄   ▌░▓█▄   ▌  ▒██ █░░▒██    ▒██ 
░▒████▓ ░▒████▓    ▒▀█░  ▒██▒   ░██▒
 ▒▒▓  ▒  ▒▒▓  ▒    ░ ▐░  ░ ▒░   ░  ░
 ░ ▒  ▒  ░ ▒  ▒    ░ ░░  ░  ░      ░
 ░ ░  ░  ░ ░  ░      ░░  ░      ░   
   ░        ░         ░         ░    
 ░        ░         ░               
    """)

if __name__ == "__main__":
    scanner = APIScanner()
    scanner.show_menu()