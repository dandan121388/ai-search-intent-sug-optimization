# Project Notes

## Project Objective

Build a local, explainable dashboard that simulates how a search platform can identify query intent, generate SUG recommendations, evaluate commercial potential, and produce operation strategy suggestions.

## User Scenario

A search product manager or search operation analyst enters a user query and wants to understand:

- what the user is likely trying to do;
- which SUG candidates should be shown;
- which recommendation words have higher commercial potential;
- where search traffic should be routed after the user clicks.

## System Workflow

```text
Query Input -> Intent Recognition -> SUG Generation -> Commercial Scoring -> Dashboard Visualization -> Strategy Recommendation
```

The current version uses a rule engine and heuristic scoring framework. It does not use real machine learning models, real search logs, or real LLM APIs.

## Key Metrics

- Intent Confidence: estimated confidence for each detected intent.
- Intent Match: how well the SUG matches the query's primary and secondary intent.
- Transaction Potential: whether the SUG can guide users toward purchase, booking, subscription, lead generation, or tool trial.
- Specificity: whether the SUG is concrete enough to capture long-tail demand.
- Commercial Keyword Strength: whether the SUG contains commercially meaningful terms.
- Overall Commercial Score: weighted score used to rank SUG candidates.

## Why This Project Matters for AI Product Commercialization

AI product commercialization is not only about generating text. Search products need to connect user intent, recommendation surfaces, ranking logic, traffic routing, and business outcomes. This project demonstrates how an AI product manager can turn query understanding into a practical operation dashboard and explainable decision framework.

## What I Would Improve Next

- Connect real search query data and SUG interaction logs.
- Use LLMs for intent recognition and SUG generation.
- Train a ranking model using click-through and conversion labels.
- Add an A/B testing simulation module.
- Add user segmentation and personalized SUG generation.
- Add CSV export for search operation workflows.
