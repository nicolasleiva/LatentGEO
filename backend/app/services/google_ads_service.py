from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from ..core.config import settings
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class GoogleAdsService:
    def __init__(self):
        self.client = None
        self.customer_id = settings.GOOGLE_ADS_CUSTOMER_ID
        
        if settings.GOOGLE_ADS_DEVELOPER_TOKEN and settings.GOOGLE_ADS_REFRESH_TOKEN:
            try:
                # Configuración desde variables de entorno
                config = {
                    "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                    "client_id": settings.GOOGLE_ADS_CLIENT_ID,
                    "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
                    "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
                    "use_proto_plus": True
                }
                if settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID:
                    config["login_customer_id"] = settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID
                    
                self.client = GoogleAdsClient.load_from_dict(config)
            except Exception as e:
                logger.error(f"Failed to initialize Google Ads Client: {e}")
        else:
            logger.warning("Google Ads credentials not found. Real data will be unavailable.")

    def get_keyword_metrics(self, keywords: List[str], location_id: str = "2840", language_id: str = "1000") -> Dict[str, Any]:
        """
        Obtiene métricas históricas (Volumen, CPC, Competencia) para una lista de keywords.
        location_id: 2840 = US
        language_id: 1000 = English
        """
        if not self.client or not self.customer_id:
            logger.warning("Google Ads Client not ready or Customer ID missing")
            return {}

        try:
            keyword_plan_idea_service = self.client.get_service("KeywordPlanIdeaService")
            request = self.client.get_type("GenerateKeywordIdeasRequest")
            request.customer_id = self.customer_id
            request.language = self.client.get_service("GoogleAdsService").language_constant_path(language_id)
            request.geo_target_constants = [self.client.get_service("GoogleAdsService").geo_target_constant_path(location_id)]
            request.include_adult_keywords = False
            
            # Usamos KeywordSeed para obtener datos de keywords específicas
            request.keyword_seed.keywords.extend(keywords)
            
            # Solo queremos métricas históricas, no ideas nuevas necesariamente, 
            # pero GenerateKeywordIdeas es la forma estándar.
            # Filtraremos los resultados para matchear nuestras keywords.

            response = keyword_plan_idea_service.generate_keyword_ideas(request=request)
            
            metrics_map = {}
            
            for idea in response:
                term = idea.text
                metrics = idea.keyword_idea_metrics
                
                # Extraer volumen promedio
                volume = metrics.avg_monthly_searches
                
                # Extraer competencia (0-100)
                competition_index = metrics.competition_index # 0-100
                
                # Extraer CPC (micros a currency)
                cpc_low = metrics.low_top_of_page_bid_micros / 1_000_000 if metrics.low_top_of_page_bid_micros else 0.0
                cpc_high = metrics.high_top_of_page_bid_micros / 1_000_000 if metrics.high_top_of_page_bid_micros else 0.0
                avg_cpc = (cpc_low + cpc_high) / 2 if cpc_high > 0 else 0.0
                
                metrics_map[term] = {
                    "volume": volume,
                    "difficulty": competition_index, # Usamos competition index como proxy de dificultad
                    "cpc": round(avg_cpc, 2)
                }
                
            return metrics_map

        except GoogleAdsException as ex:
            logger.error(f"Google Ads API Error: {ex}")
            for error in ex.failure.errors:
                logger.error(f"\tError: {error.message}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error in Google Ads Service: {e}")
            return {}
