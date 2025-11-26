# New API Endpoints

The following endpoints have been added to the backend to support the new features.

## 🔗 Backlink Analysis
- **POST** `/api/backlinks/analyze/{audit_id}?domain=example.com`
  - Triggers backlink analysis for a domain.
- **GET** `/api/backlinks/{audit_id}`
  - Retrieves stored backlinks for an audit.

## 🔍 Keyword Research
- **POST** `/api/keywords/research/{audit_id}?domain=example.com`
  - Body: `["seed", "keywords"]` (Optional)
  - Performs keyword research.
- **GET** `/api/keywords/{audit_id}`
  - Retrieves stored keywords.

## 📈 Rank Tracking
- **POST** `/api/rank-tracking/track/{audit_id}?domain=example.com`
  - Body: `["keyword1", "keyword2"]`
  - Tracks current rankings for provided keywords.
- **GET** `/api/rank-tracking/{audit_id}`
  - Retrieves ranking history.

## 🤖 LLM Visibility Tracker
- **POST** `/api/llm-visibility/check/{audit_id}?brand_name=MyBrand`
  - Body: `["query1", "query2"]`
  - Checks visibility in ChatGPT, Perplexity, etc.
- **GET** `/api/llm-visibility/{audit_id}`
  - Retrieves visibility data.

## 📝 AI Content Suggestions
- **POST** `/api/ai-content/generate/{audit_id}?domain=example.com`
  - Body: `["topic1", "topic2"]`
  - Generates content suggestions optimized for AI.
- **GET** `/api/ai-content/{audit_id}`
  - Retrieves generated suggestions.
