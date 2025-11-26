# Advanced SEO & AI Features

This update introduces 5 powerful new features to the Auditor GEO platform, moving beyond mock data to real-time, AI-driven insights.

## 1. LLM Visibility Tracker
**What it does:** Checks if your brand is recommended by AI models like ChatGPT (OpenAI) and Gemini (Google) for specific queries.
**How it works:**
- Queries the APIs directly with prompts like "What are the top companies for [Query]?".
- Analyzes the response to see if your brand is mentioned.
- Tracks visibility over time.
**Requirements:** `OPENAI_API_KEY`, `GEMINI_API_KEY`

## 2. AI Content Strategy
**What it does:** Generates content gaps, FAQ suggestions, and full article outlines based on your actual site content.
**How it works:**
- Crawls your site to understand existing content.
- Uses GPT-4o to identify missing sub-topics and questions.
- Generates detailed outlines for new content.
**Requirements:** `OPENAI_API_KEY`

## 3. Semantic Keyword Research
**What it does:** Discovers high-intent keywords relevant to your niche using AI semantic analysis.
**How it works:**
- Analyzes your domain and seed keywords.
- Generates a list of semantically related keywords with estimated intent, difficulty, and volume.
**Requirements:** `OPENAI_API_KEY`

## 4. Internal Link Audit
**What it does:** Analyzes your site's internal linking structure to find orphan pages and optimize authority flow.
**How it works:**
- Crawls your entire site (up to a limit).
- Maps all internal links.
- Identifies pages with few or no internal links.
**Requirements:** None (uses internal crawler)

## 5. Rank Tracking
**What it does:** Checks real-time rankings for your keywords on Google Search.
**How it works:**
- Uses Google Custom Search API to perform live searches.
- Reports the position of your domain for each keyword.
**Requirements:** `GOOGLE_API_KEY`, `CSE_ID` (Custom Search Engine ID)

## Setup Instructions

1.  **Environment Variables:**
    Ensure the following variables are set in your `backend/.env` file (and `docker-compose.yml`):
    ```env
    OPENAI_API_KEY=sk-... (Optional: Primary AI provider)
    GEMINI_API_KEY=AIza... (Required for Gemini Visibility. Also acts as fallback for Keywords/Content if OpenAI is missing)
    GOOGLE_API_KEY=AIza... (Required for Rank Tracking)
    CSE_ID=012345... (Required for Rank Tracking)
    ```

    **Note:** The application supports **Gemini** as a full alternative to OpenAI. If you only provide `GEMINI_API_KEY`, the system will use it for Keyword Research and AI Content Suggestions automatically. Mock data is only used if *no* AI keys are present.

2.  **Rebuild Docker:**
    Since new dependencies might have been added (though we used standard libs), rebuild the containers:
    ```bash
    docker-compose down
    docker-compose up -d --build
    ```

3.  **Access the Tools:**
    Navigate to an Audit Detail page. You will see a new "AI Audit Tools" section with links to each feature.
