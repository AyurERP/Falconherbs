# 🦅 Falcon Agency — Technical Architecture

## System Overview

Falcon Agency is a modular AI business automation system for managing Ayurvedic e-commerce. It runs as a single Python process with a 60-second main loop, controlled via WhatsApp.

## Core Components

### Entry Points
| File | Role |
|------|------|
| `main.py` | Application entry — starts Director loop + Flask webhook |
| `core/webhook.py` | Flask endpoint receiving WhatsApp webhook from Meta |

### Brain Layer
| File | Role |
|------|------|
| `core/commander.py` | AI message interpreter — classifies intent, routes, replies |
| `core/commander_intents.py` | 30+ extended intent patterns + handlers (including Inventory) |
| `core/ai_client.py` | Multi-model AI client (Claude, Gemini, fallbacks) |
| `core/memory.py` | SQLite conversation memory + topic tracking |

### Orchestration
| File | Role |
|------|------|
| `core/director.py` | Main 60-second loop — heartbeat of the system |
| `core/director_schedule.py` | Task scheduler with smart tracking |
| `core/integration_bridge.py` | Central hub connecting all tools |

### Business Tools
| File | Role |
|------|------|
| `core/woocommerce_connector.py` | WooCommerce REST API (GET + PUT) |
| `core/content_pipeline.py` | AI content generation with safety checks |
| `core/content_workflow.py` | Topic picking → generation → queue → publish |
| `core/wordpress_publisher.py` | WordPress REST API publishing |
| `core/health_scanner.py` | Website health claims scanner |
| `core/health_rewriter.py` | AI product description & title rewriter |
| `core/lead_predictor.py` | Sales velocity & stock burn-rate predictor (Pillar 1) |
| `core/revenue_tracker.py` | Revenue tracking + WooCommerce sync |
| `core/goal_tracker.py` | 30-day goal system |
| `core/profit_tracker.py` | Profit & ROI calculations |
| `core/customer_winback.py` | Inactive customer finder + email drafts |

### Infrastructure
| File | Role |
|------|------|
| `core/whatsapp.py` | Meta WhatsApp Business API sender |
| `core/approval.py` | Approval system (WhatsApp-based) |
| `core/logger.py` | Structured logging |
| `core/sentinel.py` | Security monitoring |
| `core/email_system.py` | Email sending |
| `core/image_generator.py` | AI image generation |
| `core/gsc_connector.py` | Google Search Console API |
| `agents/backup.py` | Auto-backup system |

## Data Flow

```
WhatsApp Message
     ↓
Meta Webhook → webhook.py
     ↓
Commander.handle_message()
     ↓
[1] memory.add_message()     — store in SQLite
[2] memory.track_topic()     — extract keywords, track frequency
[3] Extended Intent Check    — 30+ pattern-matched intents
[4] AI Intent Classification — Claude with rich user context
     ↓
Route to Handler → Execute via IntegrationBridge
     ↓
AI Formats Reply (mirrors owner's language)
     ↓
WhatsApp → Owner
```

## Phase Summary

| Phase | What Was Built |
|-------|---------------|
| Phase 1 | ContentPipeline, ContentWorkflow, RevenueTracker, GoalTracker, safety patterns |
| Phase 2 | WordPress publishing, content queue intents, schedule integration, safety merge |
| Phase 3 | WooCommerce PUT, HealthClaimsRewriter, Memory topics + context intelligence |
| Phase 4 | Quick-publish flow, CustomerWinback, Weekly SEO digest, Smart scheduling, Unified digest |
| Phase 5 | Title remediation, FDA disclaimer injection, Natural language help system |
| Pillar 1 | LeadPredictor (Burn Rate), Proactive Stock Alerts, Ads-Inventory Sync logic |
