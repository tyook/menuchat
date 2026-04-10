# Capacitor Mobile App Integration

## Overview

Add Capacitor to the existing Next.js frontend to deploy the QR ordering app on both Apple App Store and Google Play Store. The app serves both diners (order flow via QR) and staff (kitchen display, account management) using the existing routing — no role-based entry point changes needed.

## Goals

- Wrap the existing web app as a native iOS and Android app using Capacitor
- Add native QR code scanning via device camera
- Add push notifications for order events (order ready, new order)
- Publish to Apple App Store and Google Play Store
- Maintain the existing web deployment (Vercel/Render) unchanged

## Out of Scope

- CI/CD automation for mobile builds (can be added later with Fastlane/GitHub Actions)
- Offline support
- Automated store screenshots
- Any changes to the existing web-only user experience

## Architecture

### Target Capacitor Version

Capacitor 6 (latest stable). All plugins must be Capacitor 6 compatible.

### Dual Build Mode

The frontend supports two build modes controlled by an environment variable:

- **Web (default):** Normal Next.js build with SSR, deployed to Vercel/Render as today
- **Mobile (`NEXT_BUILD_MODE=mobile`):** Next.js static export (`output: 'export'`), outputs to `out/`, consumed by Capacitor

`next.config.mjs` conditionally sets `output: 'export'` and `images.unoptimized: true` when `NEXT_BUILD_MODE=mobile` is set.

### SPA Fallback for Dynamic Routes

The app has dynamic routes (`/order/[slug]`, `/order/[slug]/[tableId]`, `/kitchen/[slug]`, `/account/restaurants/[slug]/...`) that cannot enumerate all possible values at build time. Static export requires `generateStaticParams` for dynamic segments.

**Solution:** Configure Capacitor to use SPA fallback routing. All navigation is handled client-side:

1. Each dynamic route exports `generateStaticParams` returning an empty array and sets `export const dynamicParams = true`
2. `capacitor.config.ts` configures the server to rewrite all unmatched paths to `index.html`:
   ```ts
   server: {
     allowNavigation: ['yourdomain.com'],
   }
   ```
3. A custom `_error` or catch-all page in the static export serves as the SPA entry point, enabling client-side routing to resolve the actual page
4. All data fetching already happens client-side via React Query, so pages work correctly after client-side route resolution

### Authentication on Native

The web app uses cookie-based auth (`credentials: 'include'` with HttpOnly cookies and CSRF tokens). This **will not work** in Capacitor's WebView because the app loads from `capacitor://localhost` (iOS) / `https://localhost` (Android) — a different origin than the Django backend. Modern WebViews drop third-party cookies.

**Solution:** Dual auth strategy based on platform:

- **Web (unchanged):** Cookie-based auth as today
- **Native:** Bearer token (JWT) auth stored in `@capacitor/preferences` (encrypted device storage)
  - On login, the backend returns a JWT in the response body (in addition to setting cookies)
  - `apiFetch` in `src/lib/api.ts` detects native platform and attaches `Authorization: Bearer <token>` header instead of relying on cookies
  - CSRF tokens are not needed for Bearer auth
  - Token refresh follows the same pattern — stored and attached automatically

The backend already issues JWTs (used in WebSocket auth). The change is making `apiFetch` platform-aware and ensuring login endpoints return tokens in the response body.

### OAuth / Sign-In on Native

Google Sign-In and Apple Sign-In load via `next/Script` from CDNs and enforce origin restrictions. These scripts will not work from `capacitor://localhost`.

**Solution:** Use native Capacitor plugins for OAuth on mobile:

- **Google Sign-In:** `@codetrix-studio/capacitor-google-auth` — uses native Google Sign-In SDK
- **Apple Sign-In:** `@capacitor/sign-in-with-apple` (iOS only, hidden on Android)
- The auth hooks detect the platform and use the native plugin or web SDK accordingly
- Both return the same ID token that the backend already validates

### Capacitor Configuration

```ts
// capacitor.config.ts
import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.yourcompany.qrordering',
  appName: 'QR Ordering',
  webDir: 'out',
  server: {
    // Allow navigation to the API backend
    allowNavigation: ['yourdomain.com', 'api.yourdomain.com'],
    // Use hostname to avoid CORS issues
    hostname: 'app.localhost',
    androidScheme: 'https',
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },
  },
};

export default config;
```

### Project Structure

```
frontend/
  capacitor.config.ts          # Capacitor config (webDir: 'out')
  android/                      # Generated Android project (Gradle/Kotlin)
  ios/                          # Generated iOS project (Xcode/Swift)
  src/
    lib/
      native.ts                # Platform detection + Capacitor plugin wrappers
    hooks/
      use-native-camera.ts     # QR scanning hook (native camera on mobile, fallback on web)
      use-push-notifications.ts # Push notification registration hook
```

Capacitor is initialized inside `frontend/`. The `android/` and `ios/` directories are generated by `npx cap add ios` and `npx cap add android` and committed to version control.

### Package.json Scripts

```json
{
  "build:mobile": "cross-env NEXT_BUILD_MODE=mobile next build",
  "cap:sync": "npx cap sync",
  "cap:open:ios": "npx cap open ios",
  "cap:open:android": "npx cap open android"
}
```

Uses `cross-env` for cross-platform compatibility.

### Font Loading

The root layout uses `next/font/local` which generates CSS with absolute paths (`/_next/static/...`). In Capacitor, these resolve correctly since `webDir` points to the `out/` directory which contains the full `_next/` folder structure. However, this must be verified during the first mobile build — if fonts fail to load, the fallback is to self-host font files in `public/fonts/` and reference them with relative paths.

## Native Plugins

### 1. QR Code Scanning

**Plugin:** `@capacitor-mlkit/barcode-scanning` (Google ML Kit based, actively maintained, Capacitor 6 compatible)

**Behavior:**
- On native platforms: opens the device camera with a native barcode scanner overlay
- On web: falls back to browser-based camera access (existing behavior or hidden gracefully)
- Used when diners want to scan a QR code from within the app (e.g., at a different restaurant table)

**Hook:** `useNativeCamera()` in `src/hooks/use-native-camera.ts`
- Checks `Capacitor.isNativePlatform()` internally
- Returns `{ scan, isAvailable }` — components don't need to know about platform details

### 2. Push Notifications

**Plugin:** `@capacitor/push-notifications`

**Behavior:**
- On app launch, requests notification permission and registers with APNs (iOS) / FCM (Android)
- Sends the device token to the Django backend via `POST /api/devices/register/`
- Backend stores the token and uses it to send notifications for order events

**Hook:** `usePushNotifications()` in `src/hooks/use-push-notifications.ts`
- Handles permission request, token registration, and incoming notification events
- Only activates on native platforms (no-op on web)

### 3. Status Bar & Safe Areas

**Plugin:** `@capacitor/status-bar`

Native apps must account for iOS notch/Dynamic Island and Android status bar. The app's `viewport` meta tag already sets `viewportFit: "cover"`. Additionally:

- Use `@capacitor/status-bar` to control status bar appearance (light/dark, overlay)
- Apply CSS `env(safe-area-inset-*)` padding to the root layout to prevent content from being hidden behind system UI
- This is especially important for the kitchen display which is used in various orientations

### Platform Detection

`src/lib/native.ts` exports:
- `isNativePlatform()` — returns `true` when running inside Capacitor on a device
- Plugin wrapper functions that are safe to call on any platform

Components use these to conditionally render native-only UI (e.g., "Scan QR" button only visible in the native app).

## Backend Changes

### Device Token Storage

New Django app `notifications`:

```python
class DeviceToken(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='device_tokens',
        null=True, blank=True
    )
    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE, related_name='device_tokens',
        null=True, blank=True
    )
    token = models.TextField(unique=True)
    platform = models.CharField(max_length=10, choices=[('ios', 'iOS'), ('android', 'Android')])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

- `user` is nullable — anonymous diners (who order without an account) link via `order` instead
- `is_active` allows soft-deactivation of stale tokens rather than deletion
- Constraint: at least one of `user` or `order` must be set

### API Endpoint

`POST /api/devices/register/` — accepts `{ token, platform, order_id? }`:
- If authenticated: links to user
- If unauthenticated but `order_id` provided: links to order
- Creates or updates the device token

### Push Notification Sending

**Service:** Firebase Cloud Messaging (FCM) via `firebase-admin` Python SDK

FCM handles delivery to both iOS (via APNs) and Android devices from a single API call. The backend:
1. Receives order events (order ready, new order placed)
2. Looks up device tokens for the relevant user(s) or order
3. Sends push notification via `firebase-admin` SDK

**Firebase setup:**
- One Firebase project for the app
- Service account key stored as environment variable (never committed)
- iOS requires APNs authentication key uploaded to Firebase Console

## WebSocket Reconnection on Mobile

The kitchen display uses WebSockets (`use-websocket.ts`) for real-time order updates. On mobile, WebSocket connections are killed when the app is backgrounded.

**Solution:** Use `@capacitor/app` plugin to listen for `appStateChange` events:
- When app returns to foreground: trigger WebSocket reconnection
- The existing `use-websocket.ts` hook already has basic reconnection logic — extend it to also reconnect on the `appStateChange` resume event
- Push notifications serve as a backup notification channel when WebSocket is disconnected

## Deep Linking

Configure universal links (iOS) and app links (Android) so QR codes can open directly in the app if installed:

- URL patterns:
  - `https://yourdomain.com/order/:slug` — restaurant menu
  - `https://yourdomain.com/order/:slug/:tableId` — specific table at a restaurant
- If app is installed: opens in app
- If app is not installed: opens in browser (existing behavior)

**Configuration:**
- iOS: `apple-app-site-association` file on the web server + Associated Domains entitlement in Xcode
- Android: `assetlinks.json` on the web server + intent filters in `AndroidManifest.xml`

## App Store Deployment

### Developer Accounts

- **Apple Developer Program:** $99/year at developer.apple.com. Required for App Store submission and APNs.
- **Google Play Developer:** $25 one-time at play.google.com/console. Required for Play Store submission.

### App Identity

- **Bundle ID (iOS):** `com.<yourcompany>.qrordering` (choose during setup)
- **Application ID (Android):** same as bundle ID
- **App name:** to be decided (shown on device home screen)

### App Icons & Splash Screens

Generated using `@capacitor/assets` from a single source image (1024x1024 icon, 2732x2732 splash). The tool generates all required sizes for both platforms.

### iOS Build & Submission

1. Open `frontend/ios/App/` in Xcode
2. Configure signing (Apple Developer team, bundle ID)
3. Add privacy descriptions in `Info.plist` (camera usage, push notifications)
4. Create archive (Product > Archive)
5. Upload to App Store Connect
6. Fill in store listing (screenshots, description, privacy policy)
7. Submit for review

### Android Build & Submission

1. Open `frontend/android/` in Android Studio
2. Create signing keystore for release builds
3. Add `google-services.json` from Firebase project
4. Generate signed AAB (Build > Generate Signed Bundle)
5. Upload to Google Play Console
6. Fill in store listing (screenshots, description, privacy policy, content rating)
7. Submit for review

### Firebase Setup

1. Create a Firebase project at console.firebase.google.com
2. Add iOS app (bundle ID) — download `GoogleService-Info.plist`, add to Xcode project
3. Add Android app (application ID) — download `google-services.json`, add to Android project
4. For iOS push: upload APNs authentication key in Firebase Console > Cloud Messaging
5. Generate service account key for backend, store as env var

## Testing Strategy

- **Build verification:** CI step runs `NEXT_BUILD_MODE=mobile next build` to catch static export regressions
- **Unit tests:** hooks for push notifications and camera scanning (mock Capacitor plugins)
- **Manual testing:** run on iOS Simulator and Android Emulator via `npx cap run ios` / `npx cap run android`
- **Font/asset verification:** confirm fonts and images load correctly in first mobile build
- **Auth testing:** verify JWT auth flow works end-to-end on native (login, token storage, API calls)
- **Push notification testing:** use Firebase Console to send test notifications to specific device tokens
- **QR scanning:** test with physical device (emulators don't have real cameras)
- **Deep linking:** test with `npx uri-scheme open` and physical QR codes
- **WebSocket reconnection:** background/foreground the app and verify kitchen display reconnects

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Dynamic routes fail in static export | SPA fallback: empty `generateStaticParams` + Capacitor rewrites to `index.html` |
| Cookie auth doesn't work in WebView | Dual auth: Bearer token on native, cookies on web |
| OAuth scripts blocked in Capacitor origin | Native OAuth plugins for Google/Apple sign-in |
| Static export breaks pages relying on SSR features | Audit all pages; app is already heavily client-side rendered |
| App Store rejection for "web wrapper" | We bundle real assets + use native plugins (camera, push) — hybrid app, not a wrapper |
| Next.js Image component in static export | Set `images.unoptimized: true` in mobile build mode |
| Font loading from absolute paths | Verify in first build; fallback to `public/fonts/` if needed |
| WebSocket dropped on app background | Reconnect on `appStateChange` resume; push notifications as backup |
| Push token invalidation | Backend soft-deactivates on FCM error; app re-registers on launch |
