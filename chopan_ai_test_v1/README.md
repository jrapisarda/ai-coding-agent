# Chopan AI Outreach Assistant

A comprehensive microservices-based outreach and storytelling assistant that helps organizations create, manage, and distribute content across multiple channels.

## Features

- Content Management with AI-powered generation
- Email Campaigns with multiple ESP support
- Social Media posting and scheduling
- Prospect Discovery and scoring
- Human-in-the-Loop approval workflows
- Rate limiting and compliance checks

## Architecture

Microservices architecture with services on ports 8000-8004:
- API Gateway (8000): Central entry point
- Content Service (8001): Content generation
- Email Service (8002): Email campaigns
- Social Service (8003): Social media
- Prospect Service (8004): Prospect discovery

## Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services**
   ```bash
   # Start with Docker
   docker-compose up -d
   
   # Or start manually
   python services/api_gateway/main.py
   python services/content/main.py
   python services/email/main.py
   python services/social/main.py
   python services/prospect/main.py
   ```

4. **Check health**
   ```bash
   curl http://localhost:8000/health
   ```

## Testing

```bash
pytest tests/ -v
```

## API Documentation

Access Swagger docs at http://localhost:8000/docs when services are running.