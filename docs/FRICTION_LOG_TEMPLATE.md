# Developer Experience & Friction Log

## Overview
- **Project:** RoamReady AI
- **Evaluation Date:** October 2026
- **Architecture:** Streamable HTTP MCP Server + Web Simulator UI

## Key Observations & Friction Items

### 1. Vercel Preview Ephemerality
- **Severity:** Medium
- **Issue:** SQLite storage is temporary on Vercel preview instances, causing user profiles and saved trips to reset across serverless restarts.
- **Workaround:** Added client-facing status indicators (`temporaryStorage: true`) during demo mode to notify judges while preserving full local persistence for self-hosted instances.

### 2. Provider Rate Limits & Failure Modes
- **Severity:** Medium
- **Issue:** Google Flights and hotel data providers occasionally timeout or throw raw exceptions during peak live queries.
- **Action Taken:** Standardized error handling across all MCP tools to return safe, user-friendly fallback guidance rather than raw Python stack traces.

### 3. Non-Finite Numeric Validation
- **Severity:** High
- **Issue:** Unchecked inputs like `float('nan')` or `float('inf')` bypassed budget evaluation logic.
- **Action Taken:** Patched budget boundaries using `math.isfinite()` validation across all 5 budget calculation endpoints and added 13 automated regression tests.

## Summary & Recommendations
The Alexa+ / MCP developer setup allowed rapid tool iteration. Standardizing MCP progress reporting and providing clear offline fallback modes significantly improved overall prototype resilience.
