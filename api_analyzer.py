import requests
import json
from urllib.parse import urljoin, urlparse

class APIAnalyzerPro:
    def __init__(self):
        self.base_url = None
        self.discovered_endpoints = []
        self.tested_endpoints = []
        self.session = requests.Session()
    
    def set_base_url(self, url):
        """Establece y valida la URL base"""
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        try:
            response = self.session.head(url, timeout=5)
            if response.status_code == 200:
                self.base_url = url
                print(f"\n✅ URL base válida: {self.base_url}")
                self._discover_endpoints()
                return True
            raise ConnectionError(f"Status code: {response.status_code}")
        except Exception as e:
            print(f"\n❌ Error conectando a la URL: {str(e)}")
            return False

    def _discover_endpoints(self):
        """Descubre endpoints automáticamente mediante análisis de respuesta inicial"""
        try:
            response = self.session.get(self.base_url)
            data = response.json()

            self.discovered_endpoints = self._find_api_endpoints(data)
            
            print(f"\n🔍 Se han encontrado {len(self.discovered_endpoints)} endpoints potenciales")
            
        except Exception as e:
            print(f"\n⚠️ Error en descubrimiento automático: {str(e)}")

    def _find_api_endpoints(self, data):
        """Busca recursivamente posibles endpoints en la estructura de datos"""
        endpoints = set()
        
        def recursive_search(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key.lower() in ['url', 'endpoint', 'path', 'link']:
                        if isinstance(value, str) and self._is_valid_endpoint(value):
                            endpoints.add(value)
                    recursive_search(value)
            elif isinstance(obj, list):
                for item in obj:
                    recursive_search(item)
        
        recursive_search(data)
        return sorted(endpoints)

    def _is_valid_endpoint(self, path):
        """Valida si un path descubierto es un endpoint válido"""
        full_url = urljoin(self.base_url, path)
        parsed = urlparse(full_url)
        return parsed.netloc == urlparse(self.base_url).netloc

    def _test_endpoint(self, endpoint):
        """Ejecuta una prueba en un endpoint específico"""
        full_url = urljoin(self.base_url, endpoint)
        try:
            start_time = time.time()
            response = self.session.get(full_url)
            response_time = time.time() - start_time
            
            result = {
                'endpoint': endpoint,
                'status': response.status_code,
                'response_time': round(response_time, 2),
                'success': 200 <= response.status_code < 300,
                'content_type': response.headers.get('Content-Type', 'desconocido')
            }
            
            self.tested_endpoints.append(result)
            return result
            
        except Exception as e:
            print(f"\n⚠️ Error probando endpoint: {str(e)}")
            return None

    def show_interactive_menu(self):
        """Muestra el menú interactivo principal"""
        while True:
            print("\n" + "="*50)
            print("API Analyzer - Menú Principal")
            print(f"1. {'Establecer URL base' if not self.base_url else 'Cambiar URL base'}")
            print("2. Mostrar endpoints descubiertos")
            print("3. Probar endpoints automáticamente")
            print("4. Probar endpoint manualmente")
            print("5. Generar reporte completo")
            print("6. Salir")
            
            choice = input("\nSeleccione una opción: ").strip()
            
            if choice == '1':
                self._handle_url_input()
            elif choice == '2':
                self._show_discovered_endpoints()
            elif choice == '3':
                self._auto_test_endpoints()
            elif choice == '4':
                self._manual_test_endpoint()
            elif choice == '5':
                self.generate_report()
            elif choice == '6':
                print("\n¡nv!")
                break
            else:
                print("\nOpción inválida")

    def _handle_url_input(self):
        url = input("\nIngrese la URL base de la API: ").strip()
        if url:
            if self.set_base_url(url):
                self._discover_endpoints()

    def _show_discovered_endpoints(self):
        if not self.discovered_endpoints:
            print("\nNo se han descubierto endpoints automáticamente")
            return
            
        print("\nEndpoints descubiertos:")
        for i, endpoint in enumerate(self.discovered_endpoints[:25], 1):
            print(f"{i}. {endpoint}")
        print(f"\nMostrando {len(self.discovered_endpoints[:25])} de {len(self.discovered_endpoints)} encontrados")

    def _auto_test_endpoints(self):
        if not self.discovered_endpoints:
            print("\nPrimero descubre endpoints automáticamente")
            return
            
        print("\n🔧 Probando endpoints descubiertos...")
        for endpoint in self.discovered_endpoints[:10]:  # Limitar a primeros 10
            result = self._test_endpoint(endpoint)
            if result:
                status = "✅" if result['success'] else "❌"
                print(f"{status} {endpoint} - {result['status']} ({result['response_time']}s)")

    def _manual_test_endpoint(self):
        endpoint = input("\nIngrese el endpoint completo a probar (ej: /api/v1/users): ").strip()
        result = self._test_endpoint(endpoint)
        if result:
            print("\nResultado de la prueba:")
            print(f"Estado: {result['status']} | Tiempo: {result['response_time']}s")
            print(f"Tipo contenido: {result['content_type']}")
      
    def _find_api_endpoints(self, data):
        """Versión mejorada que combina ambos métodos"""
        endpoints = set()
        
        def recursive_search(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key.lower() in ['url', 'endpoint', 'path', 'link', 'html_url', 'api']:
                        self._add_endpoint(value, endpoints)
                    
                    if isinstance(value, str):
                        self._add_endpoint(value, endpoints)
                    
                    recursive_search(value)
            elif isinstance(obj, list):
                for item in obj:
                    recursive_search(item)
        
        recursive_search(data)
        return sorted(endpoints)
    
    def _add_endpoint(self, value, endpoints):
        """Valida y agrega endpoints encontrados"""
        if isinstance(value, str):
            # Filtrar URLs no relevantes
            if any(p in value for p in ['api.github.com', 'http']):
                if self._is_valid_endpoint(value):
                    endpoints.add(value)

    def generate_report(self):
        if not self.tested_endpoints:
            print("\nNo hay endpoints probados para generar reporte")
            return
            
        report = {
            'base_url': self.base_url,
            'tested_endpoints': self.tested_endpoints,
            'success_rate': len([e for e in self.tested_endpoints if e['success']]) / len(self.tested_endpoints),
            'average_response_time': round(sum(e['response_time'] for e in self.tested_endpoints) / len(self.tested_endpoints), 2)
        }
        
        filename = f"api_report_{int(time.time())}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\n📊 Reporte generado: {filename}")

if __name__ == "__main__":
    import time
    analyzer = APIAnalyzerPro()
    analyzer.show_interactive_menu()