# ai-qr-ordering
AI-powered QR code ordering system for restaurants. Customers scan, speak or type their order, and an LLM parses it into structured items.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (for Postgres and Redis)

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys:
   ```
   cp .env.example .env
   ```

2. Start Postgres and Redis:
   ```
   docker-compose up -d db redis
   ```

3. Install backend dependencies and run migrations:
   ```
   cd backend
   poetry install
   python manage.py migrate
   ```

4. Install frontend dependencies:
   ```
   cd frontend
   npm install
   ```

5. Set up Stripe (for subscription billing):

   a. Create a [Stripe account](https://dashboard.stripe.com/register) and switch to **Test mode**.

   b. Copy your **Secret key** from Developers > API keys and set it in `.env`:
      ```
      STRIPE_SECRET_KEY=sk_test_...
      ```

   c. Copy your **Publishable key** and set it in `frontend/.env.local`:
      ```
      NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
      ```

   d. Create three products in **Product catalog > Add product** with two prices each:

      | Product | Monthly price | Annual price |
      |---------|--------------|--------------|
      | Starter | $49/month    | $480/year    |
      | Growth  | $99/month    | $984/year    |
      | Pro     | $199/month   | $1,992/year  |

   e. Copy each price ID (starts with `price_`) and set them in `.env`:
      ```
      STRIPE_PRICE_STARTER_MONTHLY=price_...
      STRIPE_PRICE_STARTER_ANNUAL=price_...
      STRIPE_PRICE_GROWTH_MONTHLY=price_...
      STRIPE_PRICE_GROWTH_ANNUAL=price_...
      STRIPE_PRICE_PRO_MONTHLY=price_...
      STRIPE_PRICE_PRO_ANNUAL=price_...
      ```

   f. Install the [Stripe CLI](https://docs.stripe.com/stripe-cli) and forward webhooks to your local backend:
      ```
      brew install stripe/stripe-cli/stripe
      stripe login
      stripe listen --forward-to localhost:5005/api/order/webhook/stripe/
      ```
      Copy the webhook signing secret it prints and set it in `.env`:
      ```
      STRIPE_WEBHOOK_SECRET=whsec_...
      ```

## Running

Start the backend (port 5005):
```
cd backend
./manage.py runserver 5005
```

Start the frontend (port 3001):
```
cd frontend
yarn dev -- -p 3001
```

Start Stripe webhook forwarding (in a separate terminal):
```
stripe listen --forward-to localhost:5005/api/order/webhook/stripe/
```

| Service  | URL                     |
|----------|-------------------------|
| Backend  | http://localhost:5005   |
| Frontend | http://localhost:3001   |
