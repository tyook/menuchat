# Order Queue & Estimated Wait Time

## Overview

Enable customers to see restaurant busyness before placing an order and track their queue position with estimated wait time after ordering. This addresses the core UX challenge of a QR ordering system that accepts orders from customers outside the restaurant, where high volume and long waits are expected.

## Requirements

- **Pre-order**: Display a traffic light busyness indicator (green/yellow/red) with estimated wait on the ConfirmationStep
- **Post-order**: Display a progress bar (Confirmed → Preparing → Ready → Completed), queue position, and estimated wait on the SubmittedStep
- **Real-time updates**: WebSocket push with polling fallback for post-order tracking
- **Wait time calculation**: Owner-configured estimate initially, switch to historical averages after 50 completed orders

## Architecture: Computed Queue (No New Model)

Queue position and wait time are computed on-the-fly from existing Order data. No new queue model — the Order model's `created_at` and status fields naturally define queue ordering. Historical averages and busyness levels are cached in Redis, refreshed by a Celery periodic task.

## Data Model Changes

### Order model additions (`backend/orders/models.py`)

| Field | Type | Description |
|-------|------|-------------|
| `confirmed_at` | DateTimeField, nullable | Set when status moves to `confirmed` |
| `preparing_at` | DateTimeField, nullable | Set when status moves to `preparing` |
| `ready_at` | DateTimeField, nullable | Set when status moves to `ready` |
| `completed_at` | DateTimeField, nullable | Set when status moves to `completed` |

These timestamps power historical wait time calculations.

### Restaurant model additions (`backend/restaurants/models.py`)

| Field | Type | Description |
|-------|------|-------------|
| `estimated_minutes_per_order` | PositiveIntegerField, default=10 | Owner-configurable fallback estimate |
| `use_historical_estimates` | BooleanField, default=False | Flipped to True automatically once 50 orders have completed |

### Redis cached values (per restaurant)

| Key | Description |
|-----|-------------|
| `queue:{slug}:avg_prep_time` | Rolling average minutes from confirmed → ready |
| `queue:{slug}:active_count` | Count of orders in confirmed/preparing status |
| `queue:{slug}:busyness` | Computed traffic light level (green/yellow/red) |

## QueueService (`backend/orders/queue_service.py`)

### Methods

- **`get_queue_position(order)`** — Counts orders for that restaurant with status in (`confirmed`, `preparing`) and `created_at` before this order's `created_at`. Returns 1-based integer position.

- **`get_estimated_wait(restaurant, queue_position)`** — If `use_historical_estimates` is True, uses cached `avg_prep_time * queue_position`. Otherwise, uses `estimated_minutes_per_order * queue_position`. Returns minutes as integer.

- **`get_busyness(restaurant)`** — Reads cached `active_count` and maps to traffic light:
  - **Green**: 0-5 active orders (or < 15 min estimated wait)
  - **Yellow**: 6-15 active orders (or 15-30 min)
  - **Red**: 16+ active orders (or 30+ min)
  - Thresholds hardcoded for v1.

- **`get_restaurant_queue_info(restaurant)`** — Returns busyness level + estimated wait for ConfirmationStep. Reads from Redis cache.

- **`get_order_queue_info(order)`** — Returns queue position + estimated wait + order status for SubmittedStep. Computes position live, wait from cache.

### Celery periodic task (every 5 minutes)

**`update_queue_stats`** — For each restaurant with active orders:
1. Count active orders → cache `active_count`
2. Compute rolling average prep time from last 50 completed orders (within last 30 days) → cache `avg_prep_time`
3. Compute busyness level → cache `busyness`
4. Check if restaurant has 50+ completed orders and flip `use_historical_estimates` if needed

This task only refreshes cached averages. Real-time queue position updates are pushed instantly via WebSocket when kitchen staff changes order status.

## API Endpoints

### New REST endpoints

**`GET /api/order/<slug>/queue-info/`** — Restaurant busyness (pre-order, public).

Response:
```json
{
  "busyness": "yellow",
  "estimated_wait_minutes": 20,
  "active_orders": 12
}
```

**`GET /api/order/<slug>/status/<order_id>/queue/`** — Order queue position (post-order, public; UUID serves as access token).

Response:
```json
{
  "queue_position": 5,
  "estimated_wait_minutes": 15,
  "status": "confirmed",
  "busyness": "yellow"
}
```

### WebSocket

**`CustomerOrderConsumer`** at `ws/order/<slug>/<order_id>/`

- On connect: joins channel group `customer_{order_id}`
- No auth required (UUID order ID serves as access token)
- Receives pushed updates on status change or queue position shift
- Message format:
```json
{
  "type": "queue_update",
  "queue_position": 3,
  "estimated_wait_minutes": 10,
  "status": "preparing"
}
```

### Broadcasting changes (`broadcast.py`)

Extend `broadcast_order_to_kitchen()` to also:
1. Push update to `customer_{order_id}` group for the changed order
2. Recalculate and push updated queue positions to all customers with orders ahead in the queue (orders at that restaurant with status `confirmed` or `preparing` and `created_at` after the changed order)
3. Skip orders already in `ready` or `completed` status

### Polling fallback

If WebSocket connection fails, frontend polls `GET /api/order/<slug>/status/<order_id>/queue/` every 15 seconds.

## Frontend Components

### ConfirmationStep changes (`frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`)

Add a busyness banner at the top of the page, above order items:
- Calls `GET /api/order/<slug>/queue-info/` on mount
- Displays traffic light: green circle + "Short wait (~X min)", yellow + "Moderate wait (~X min)", red + "Busy — ~X min wait"
- Subtle, non-blocking — informational only

### SubmittedStep changes (`frontend/src/app/order/[slug]/components/SubmittedStep.tsx`)

Replace current simple confirmation with a live order tracker:
- **Progress bar** — 4 steps: Confirmed → Preparing → Ready → Completed. Active step highlighted, completed steps checked.
- **Queue position** — "You are #5 in line"
- **Estimated wait** — "~15 minutes estimated wait"
- **Live indicator** — green dot + "Live updates active" (WebSocket) or gray "Updating..." (polling)
- When order reaches "ready": queue info replaced with "Your order is ready for pickup!"
- When "completed": "Order complete. Thank you!"

### New hooks

**`use-order-queue.ts`**
- Manages WebSocket connection to `ws/order/<slug>/<order_id>/`
- On WebSocket failure, starts polling every 15 seconds
- Reconnection attempted every 3 seconds (matches existing pattern)
- Returns `{ queuePosition, estimatedWait, status, busyness, isConnected }`

**`use-restaurant-busyness.ts`**
- React Query hook calling the queue-info endpoint
- Returns `{ busyness, estimatedWait, isLoading }`

## Error Handling & Edge Cases

| Scenario | Behavior |
|----------|----------|
| WebSocket disconnects | Auto-switch to polling every 15s; indicator changes to "Updating..." |
| WebSocket reconnects | Resume push updates; indicator returns to "Live updates active" |
| No active orders | Busyness banner shows green: "No wait right now" |
| No completed orders, no configured estimate | Default to 10 minutes per order |
| Redis cache empty (cold start) | Compute on-the-fly and cache the result |
| Order reaches "ready" | Queue position/wait disappear; show "Your order is ready for pickup!" |
| Order reaches "completed" | Show "Order complete. Thank you!" |
| Historical data staleness | Only use orders from last 30 days for averages |

## Testing Strategy

### Backend unit tests
- `QueueService.get_queue_position()` — correct position with multiple orders in various statuses
- `QueueService.get_estimated_wait()` — owner-configured vs historical calculation, switchover at 50 orders
- `QueueService.get_busyness()` — green/yellow/red thresholds
- `update_order_status()` — status timestamps set correctly on transitions
- Celery task — cache values computed and stored correctly

### Backend integration tests
- Queue info endpoint returns correct busyness for various order loads
- Order queue endpoint returns correct position and wait time
- WebSocket consumer sends queue updates on status change
- Broadcasting recalculates positions for affected customers only

### Frontend tests
- `use-order-queue` hook — WebSocket connection, fallback to polling, state updates
- `use-restaurant-busyness` hook — API call and data mapping
- Busyness banner renders correct color/text per level
- Progress bar renders correct state per order status
- Queue position and wait time update on new data
