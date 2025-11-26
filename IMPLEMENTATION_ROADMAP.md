# 🗺️ ROADMAP DE IMPLEMENTACIÓN - 90 DÍAS
## De MVP a Producto Competitivo

*Plan detallado para implementar features prioritarias*  
*Timeline: 3 meses | Budget: $150-200/mes en APIs*

---

## 📅 OVERVIEW DEL ROADMAP

```
MES 1 (Semanas 1-4)          MES 2 (Semanas 5-8)         MES 3 (Semanas 9-12)
├─ Auth + Security           ├─ GEO Features Únicos      ├─ Polish + Launch
├─ Keywords Básicos          ├─ Rank Tracking            ├─ White-Label
└─ MVP Lanzable              └─ Backlink Metrics         └─ Marketing Ready
```

---

## 🎯 MES 1: FOUNDATION & MVP (40 horas)

### Semana 1-2: Autenticación & Seguridad (20h)

#### Feature: JWT Authentication + Multi-User

**Archivos a crear/modificar:**
```python
# backend/app/models/__init__.py
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(String, default="user")  # "admin", "user", "viewer"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relación con auditorías
    audits = relationship("Audit", back_populates="user")

# backend/app/core/auth.py
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# backend/app/api/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@router.post("/register")
async def register(
    email: str,
    password: str,
    full_name: str,
    db: Session = Depends(get_db)
):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = get_password_hash(password)
    user = User(email=email, hashed_password=hashed_password, full_name=full_name)
    db.add(user)
    db.commit()
    
    return {"message": "User created successfully"}

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect credentials")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials"
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

# Proteger rutas existentes
# backend/app/api/routes/audits.py (modificar)
@router.post("/")
async def create_audit(
    audit_data: AuditCreate,
    current_user: User = Depends(get_current_user),  # ← AÑADIR
    db: Session = Depends(get_db)
):
    # Asociar auditoría con usuario
    audit = Audit(**audit_data.dict(), user_id=current_user.id)
    db.add(audit)
    db.commit()
    return audit
```

**Dependencias nuevas (requirements.txt):**
```
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
python-multipart==0.0.6
```

**Tests a crear:**
```python
# backend/tests/test_auth.py
def test_register_user():
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "test123",
        "full_name": "Test User"
    })
    assert response.status_code == 200

def test_login_user():
    response = client.post("/auth/login", data={
        "username": "test@example.com",
        "password": "test123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_protected_route():
    # Sin token
    response = client.post("/audits/")
    assert response.status_code == 401
    
    # Con token
    token = get_test_token()
    response = client.post("/audits/", 
        headers={"Authorization": f"Bearer {token}"},
        json={...}
    )
    assert response.status_code == 200
```

**Estimación:** 20 horas  
**Prioridad:** 🔴 CRÍTICA  
**Output:** Sistema de autenticación completo + usuarios protegidos

---

### Semana 3-4: Keyword Research Básico (20h)

#### Feature: Integración con DataForSEO API

**Archivos a crear:**

```python
# backend/app/services/keyword_service.py
import aiohttp
from typing import List, Dict, Optional
import os

class KeywordService:
    """Servicio para keyword research usando DataForSEO API."""
    
    API_URL = "https://api.dataforseo.com/v3"
    
    def __init__(self):
        self.login = os.getenv("DATAFORSEO_LOGIN")
        self.password = os.getenv("DATAFORSEO_PASSWORD")
    
    async def get_keyword_data(
        self, 
        keyword: str, 
        location: str = "United States"
    ) -> Dict:
        """
        Obtiene volumen, dificultad y CPC para un keyword.
        
        Returns:
            {
                'keyword': str,
                'search_volume': int,
                'difficulty': int (0-100),
                'cpc': float,
                'competition': str,
                'related_keywords': List[str]
            }
        """
        url = f"{self.API_URL}/keywords_data/google_ads/search_volume/live"
        
        payload = [{
            "keywords": [keyword],
            "location_name": location,
            "language_name": "English"
        }]
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, 
                json=payload,
                auth=aiohttp.BasicAuth(self.login, self.password)
            ) as resp:
                data = await resp.json()
                
        if data['status_code'] == 20000:
            result = data['tasks'][0]['result'][0]
            return {
                'keyword': keyword,
                'search_volume': result.get('search_volume', 0),
                'difficulty': result.get('keyword_difficulty', 0),
                'cpc': result.get('cpc', 0.0),
                'competition': result.get('competition', 'N/A'),
                'related_keywords': []  # Implementar en siguiente iteración
            }
        
        raise Exception(f"API Error: {data['status_message']}")
    
    async def get_keyword_suggestions(
        self, 
        seed_keyword: str, 
        limit: int = 50
    ) -> List[Dict]:
        """
        Obtiene sugerencias de keywords relacionadas.
        """
        url = f"{self.API_URL}/keywords_data/google_ads/keywords_for_keywords/live"
        
        payload = [{
            "keywords": [seed_keyword],
            "location_name": "United States",
            "language_name": "English",
            "include_seed_keyword": True,
            "include_serp_info": False,
            "limit": limit
        }]
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                auth=aiohttp.BasicAuth(self.login, self.password)
            ) as resp:
                data = await resp.json()
        
        if data['status_code'] == 20000:
            items = data['tasks'][0]['result'][0]['items']
            return [
                {
                    'keyword': item['keyword'],
                    'search_volume': item.get('search_volume', 0),
                    'cpc': item.get('cpc', 0.0),
                    'competition': item.get('competition', 'N/A')
                }
                for item in items
            ]
        
        return []

# backend/app/api/routes/keywords.py
from fastapi import APIRouter, Depends
from app.services.keyword_service import KeywordService

router = APIRouter(prefix="/keywords", tags=["Keywords"])

@router.get("/data")
async def get_keyword_data(
    keyword: str,
    location: str = "United States",
    current_user: User = Depends(get_current_user)
):
    """Obtiene datos de un keyword específico."""
    service = KeywordService()
    data = await service.get_keyword_data(keyword, location)
    return data

@router.get("/suggestions")
async def get_keyword_suggestions(
    seed_keyword: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Obtiene sugerencias de keywords relacionadas."""
    service = KeywordService()
    suggestions = await service.get_keyword_suggestions(seed_keyword, limit)
    return {"seed": seed_keyword, "suggestions": suggestions}

# Registro en main.py
from app.api.routes import keywords
app.include_router(keywords.router)
```

**Frontend Integration:**

```typescript
// frontend/components/KeywordResearch.tsx
import React, { useState } from 'react';
import axios from 'axios';

export const KeywordResearch = () => {
  const [keyword, setKeyword] = useState('');
  const [data, setData] = useState(null);
  
  const handleSearch = async () => {
    const response = await axios.get('/api/keywords/data', {
      params: { keyword },
      headers: { Authorization: `Bearer ${token}` }
    });
    setData(response.data);
  };
  
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">Keyword Research</h2>
      <div className="flex gap-4 mb-6">
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="Enter keyword..."
          className="border rounded px-4 py-2 flex-1"
        />
        <button
          onClick={handleSearch}
          className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700"
        >
          Search
        </button>
      </div>
      
      {data && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="grid grid-cols-4 gap-4">
            <div>
              <p className="text-gray-600 text-sm">Search Volume</p>
              <p className="text-2xl font-bold">{data.search_volume}</p>
            </div>
            <div>
              <p className="text-gray-600 text-sm">Difficulty</p>
              <p className="text-2xl font-bold">{data.difficulty}/100</p>
            </div>
            <div>
              <p className="text-gray-600 text-sm">CPC</p>
              <p className="text-2xl font-bold">${data.cpc}</p>
            </div>
            <div>
              <p className="text-gray-600 text-sm">Competition</p>
              <p className="text-2xl font-bold">{data.competition}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
```

**.env variables:**
```bash
DATAFORSEO_LOGIN=your_login
DATAFORSEO_PASSWORD=your_password
```

**Costo:** $100-150/mes (DataForSEO plan básico)  
**Estimación:** 20 horas  
**Prioridad:** 🔴 ALTA  
**Output:** Keyword research funcional con volumen + dificultad

---

## 🚀 MES 2: DIFERENCIACIÓN GEO (50 horas)

### Semana 5-6: LLM Visibility Tracker (30h)

#### Feature: Monitoreo de visibilidad en ChatGPT, Perplexity, Google SGE

**Esta es TU ventaja competitiva única** ⭐

```python
# backend/app/services/llm_visibility_service.py
import asyncio
import aiohttp
from typing import List, Dict
import json

class LLMVisibilityService:
    """
    Servicio para trackear visibilidad en LLMs (ChatGPT, Perplexity, Google SGE).
    
    Esta es la FEATURE ÚNICA que te diferencia de Semrush/Ahrefs.
    """
    
    async def check_chatgpt_visibility(
        self,
        domain: str,
        queries: List[str]
    ) -> Dict:
        """
        Verifica si el dominio aparece en respuestas de ChatGPT.
        
        NOTA: Requiere API de OpenAI con acceso a browsing.
        """
        results = []
        
        for query in queries:
            # Usar OpenAI API con browsing enabled
            response = await self._query_openai(query, browsing=True)
            
            # Analizar si domain aparece en la respuesta
            is_mentioned = domain in response['answer']
            
            # Extraer citations si existen
            citations = self._extract_citations(response['answer'], domain)
            
            results.append({
                'query': query,
                'mentioned': is_mentioned,
                'citations': citations,
                'position': self._get_citation_position(citations) if citations else None,
                'full_response': response['answer'][:500]  # Preview
            })
        
        return {
            'domain': domain,
            'llm': 'ChatGPT',
            'queries_tested': len(queries),
            'mentions_found': sum(1 for r in results if r['mentioned']),
            'visibility_score': self._calculate_visibility_score(results),
            'results': results,
            'tested_at': datetime.utcnow().isoformat()
        }
    
    async def check_perplexity_visibility(
        self,
        domain: str,
        queries: List[str]
    ) -> Dict:
        """
        Verifica visibilidad en Perplexity.ai
        
        Perplexity tiene API pública: https://docs.perplexity.ai
        """
        api_key = os.getenv("PERPLEXITY_API_KEY")
        url = "https://api.perplexity.ai/chat/completions"
        
        results = []
        
        for query in queries:
            payload = {
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [{"role": "user", "content": query}],
                "return_citations": True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}"}
                ) as resp:
                    data = await resp.json()
            
            answer = data['choices'][0]['message']['content']
            citations = data['choices'][0]['message'].get('citations', [])
            
            domain_cited = any(domain in cite for cite in citations)
            
            results.append({
                'query': query,
                'mentioned': domain in answer,
                'cited': domain_cited,
                'citations': [c for c in citations if domain in c],
                'answer_preview': answer[:500]
            })
        
        return {
            'domain': domain,
            'llm': 'Perplexity',
            'queries_tested': len(queries),
            'citations_found': sum(1 for r in results if r['cited']),
            'visibility_score': self._calculate_visibility_score(results),
            'results': results
        }
    
    async def check_google_sge_visibility(
        self,
        domain: str,
        queries: List[str]
    ) -> Dict:
        """
        Verifica aparición en Google AI Overviews (SGE).
        
        Requiere scraping de Google SERP + detección de AI Overview.
        """
        results = []
        
        for query in queries:
            # Usar SerpApi o similar para obtener SGE
            serp_data = await self._get_google_serp(query, include_ai_overview=True)
            
            ai_overview = serp_data.get('ai_overview', {})
            
            if ai_overview:
                sources = ai_overview.get('sources', [])
                domain_mentioned = any(domain in source.get('url', '') for source in sources)
                
                results.append({
                    'query': query,
                    'sge_present': True,
                    'mentioned': domain_mentioned,
                    'sources': [s for s in sources if domain in s.get('url', '')],
                    'snippet': ai_overview.get('snippet', '')
                })
            else:
                results.append({
                    'query': query,
                    'sge_present': False,
                    'mentioned': False
                })
        
        return {
            'domain': domain,
            'llm': 'Google SGE',
            'queries_tested': len(queries),
            'sge_appearances': sum(1 for r in results if r.get('sge_present')),
            'mentions_found': sum(1 for r in results if r.get('mentioned')),
            'visibility_score': self._calculate_visibility_score(results),
            'results': results
        }
    
    def _calculate_visibility_score(self, results: List[Dict]) -> float:
        """
        Calcula score de visibilidad (0-100).
        
        Factores:
        - % de queries donde aparece el dominio
        - Posición en citations (si aplica)
        - Presencia vs ausencia de SGE
        """
        if not results:
            return 0.0
        
        mention_rate = sum(1 for r in results if r.get('mentioned', False)) / len(results)
        return round(mention_rate * 100, 1)
    
    async def run_full_visibility_audit(
        self,
        domain: str,
        queries: List[str]
    ) -> Dict:
        """
        Ejecuta auditoría completa de visibilidad en todos los LLMs.
        """
        chatgpt_data, perplexity_data, sge_data = await asyncio.gather(
            self.check_chatgpt_visibility(domain, queries),
            self.check_perplexity_visibility(domain, queries),
            self.check_google_sge_visibility(domain, queries)
        )
        
        overall_score = (
            chatgpt_data['visibility_score'] +
            perplexity_data['visibility_score'] +
            sge_data['visibility_score']
        ) / 3
        
        return {
            'domain': domain,
            'overall_visibility_score': round(overall_score, 1),
            'chatgpt': chatgpt_data,
            'perplexity': perplexity_data,
            'google_sge': sge_data,
            'recommendations': self._generate_recommendations(
                chatgpt_data, perplexity_data, sge_data
            )
        }

# backend/app/api/routes/geo.py
from fastapi import APIRouter, Depends, BackgroundTasks
from app.services.llm_visibility_service import LLMVisibilityService

router = APIRouter(prefix="/geo", tags=["GEO Features"])

@router.post("/visibility-audit")
async def run_visibility_audit(
    domain: str,
    queries: List[str],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Ejecuta auditoría de visibilidad en LLMs.
    
    Esta es LA feature que te hace único en el mercado.
    """
    service = LLMVisibilityService()
    
    # Ejecutar en background (puede tomar varios minutos)
    background_tasks.add_task(
        service.run_full_visibility_audit,
        domain,
        queries
    )
    
    return {
        "message": "Visibility audit started",
        "domain": domain,
        "queries_count": len(queries),
        "estimated_time": f"{len(queries) * 3} seconds"
    }
```

**Modelo de datos:**

```python
# backend/app/models/__init__.py
class LLMVisibilityAudit(Base):
    __tablename__ = "llm_visibility_audits"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    domain = Column(String, index=True)
    queries = Column(JSON)  # List of queries tested
    
    chatgpt_score = Column(Float)
    perplexity_score = Column(Float)
    google_sge_score = Column(Float)
    overall_score = Column(Float)
    
    results = Column(JSON)  # Full results
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="llm_audits")
```

**.env additions:**
```bash
OPENAI_API_KEY=your_key
PERPLEXITY_API_KEY=your_key
SERPAPI_KEY=your_key  # Para Google SGE
```

**Costo adicional:** $50-100/mes (OpenAI + Perplexity + SerpApi)  
**Estimación:** 30 horas  
**Prioridad:** ⭐ **MÁXIMA** (esto es tu diferenciador #1)  
**Output:** Tracking de visibilidad en 3 LLMs principales

---

### Semana 7-8: AI Content Suggestions (20h)

#### Feature: Sugerencias automáticas para optimizar contenido para LLMs

```python
# backend/app/services/ai_content_optimizer.py
class AIContentOptimizer:
    """
    Genera sugerencias de optimización para mejorar citabilidad en LLMs.
    """
    
    def analyze_content_for_llm_optimization(
        self,
        html: str,
        target_domain: str
    ) -> Dict:
        """
        Analiza contenido y genera sugerencias concretas.
        """
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        
        suggestions = []
        
        # 1. FAQ Structure Analysis
        has_faqs = self._detect_faq_structure(soup)
        if not has_faqs:
            suggestions.append({
                'type': 'STRUCTURE',
                'priority': 'HIGH',
                'title': 'Add FAQ Section',
                'description': 'LLMs prefer Q&A format for direct answers',
                'example': self._generate_faq_example(text),
                'impact': 'Increases likelihood of being cited by 3-5x'
            })
        
        # 2. Entity Optimization
        entities = self._extract_entities(text)
        missing_entity_context = self._check_entity_context(entities)
        if missing_entity_context:
            suggestions.append({
                'type': 'ENTITIES',
                'priority': 'MEDIUM',
                'title': 'Add Entity Context',
                'description': f'Define these entities clearly: {missing_entity_context}',
                'example': self._generate_entity_definition_example(missing_entity_context[0])
            })
        
        # 3. Citation-Worthy Stats
        has_stats = self._detect_statistics(text)
        if not has_stats:
            suggestions.append({
                'type': 'DATA',
                'priority': 'HIGH',
                'title': 'Add Data Points & Statistics',
                'description': 'LLMs prioritize content with verifiable data',
                'example': self._suggest_stat_integration(target_domain)
            })
        
        # 4. TL;DR / Summary
        has_summary = self._detect_tldr(soup)
        if not has_summary:
           suggestions.append({
                'type': 'STRUCTURE',
                'priority': 'CRITICAL',
                'title': 'Add TL;DR Summary',
                'description': 'Brief summary at the top helps LLMs extract key points',
                'example': self._generate_tldr_from_content(text)
            })
        
        return {
            'score': self._calculate_llm_readiness_score(suggestions),
            'suggestions': suggestions,
            'estimated_improvement': f"+{len(suggestions) * 15}% visibility"
        }
```

---

## 🏁 MES 3: POLISH & LAUNCH (30 horas)

### Semana 9-10: Rank Tracking + Backlink Metrics (20h)

*Integración con SerpApi + Moz API (código similar a ejemplos anteriores)*

### Semana 11-12: White-Label + Marketing Ready (10h)

*Configuración de marca personalizada + landing page*

---

## 💰 BUDGET TOTAL (3 MESES)

| Concepto | Costo/mes | Total 3 meses |
|----------|-----------|---------------|
| **DataForSEO** (Keywords) | $100-150 | $300-450 |
| **Perplexity API** | $20-40 | $60-120 |
| **SerpApi** (SGE + Ranking) | $50-75 | $150-225 |
| **OpenAI** (LLM Visibility) | $20-50 | $60-150 |
| **Moz/Ahrefs API** (Backlinks) | $99 | $297 |
| **TOTAL** | **$289-414/mes** | **$867-1,242** |

---

## 🎯 DELIVERABLES AL FINAL DE 90 DÍAS

✅ Sistema de autenticación completo  
✅ Keyword research con volumen + dificultad  
✅ **LLM Visibility Tracker** (ChatGPT, Perplexity, SGE) ⭐  
✅ **AI Content Optimizer** ⭐  
✅ Rank tracking básico  
✅ Backlink metrics básicas  
✅ White-label ready  
✅ 100+ tests automatizados  

**Producto lanzable con diferenciación clara vs competencia** 🚀

---

¿Comenzamos con la Semana 1? Puedo ayudarte a implementar el sistema de autenticación ahora mismo. 💪
