# Capacitor Mobile App — Deployment README

This document covers the full architecture, setup, build, and deployment process for the MenuChat native mobile apps (iOS and Android), built with Capacitor 6 wrapping the existing Next.js frontend.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [How the Dual Build Works](#how-the-dual-build-works)
3. [Prerequisites](#prerequisites)
4. [Initial Setup (First Time)](#initial-setup-first-time)
5. [Firebase Setup](#firebase-setup)
6. [Google OAuth Setup (Native)](#google-oauth-setup-native)
7. [Apple Sign-In Setup (Native)](#apple-sign-in-setup-native)
8. [App Icons and Splash Screens](#app-icons-and-splash-screens)
9. [Building for iOS](#building-for-ios)
10. [Building for Android](#building-for-android)
11. [Push Notifications](#push-notifications)
12. [Deep Linking](#deep-linking)
13. [Environment Variables Reference](#environment-variables-reference)
14. [Development Workflow](#development-workflow)
15. [How Auth Works on Native vs Web](#how-auth-works-on-native-vs-web)
16. [Key Files and Their Purpose](#key-files-and-their-purpose)
17. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                   Capacitor Shell                        │
│  ┌────────────┐    ┌─────────────────────────────────┐   │
│  │ Native iOS │    │ Next.js Static Export (out/)     │   │
│  │ / Android  │◄──►│ - Client-side rendered           │   │
│  │ Plugins    │    │ - Bearer token auth              │   │
│  └────────────┘    │ - Native plugin bridges          │   │
│       │            └─────────────────────────────────┘   │
│       │                                                  │
│  Push Notifications (FCM)                                │
│  QR Scanner (@capacitor-mlkit/barcode-scanning)          │
│  Secure Storage (@capacitor/preferences)                 │
│  Status Bar, Deep Links, App Lifecycle                   │
└──────────────────────────────────────────────────────────┘
         │
         ▼  HTTPS (Bearer token)
┌──────────────────────────────────────────────────────────┐
│  Django Backend                                          │
│  - JWT auth (cookies for web, Bearer for native)         │
│  - /api/devices/register/ (FCM token registration)       │
│  - Firebase Admin SDK → push notifications               │
│  - WebSocket (channels) for real-time kitchen updates    │
└──────────────────────────────────────────────────────────┘
```

**Key design decisions:**

- **Dual build mode:** The same Next.js codebase serves both web (SSR) and mobile (static export). The `NEXT_BUILD_MODE=mobile` env var switches to `output: 'export'`.
- **Auth divergence:** Web uses httpOnly cookies + CSRF. Native uses `Authorization: Bearer` headers with tokens stored in `@capacitor/preferences`. The backend returns tokens in the response body of all login/register endpoints so native clients can capture them.
- **Static export + SPA fallback:** Dynamic routes (e.g. `/order/[slug]`) use a server wrapper + `generateStaticParams` pattern with a placeholder. Capacitor serves `404.html` for unmatched routes, which redirects to `/` where Next.js client-side routing takes over.

---

## How the Dual Build Works

| Command | Mode | Output | Auth | Use Case |
|---------|------|--------|------|----------|
| `yarn build` | SSR | `.next/` | Cookies + CSRF | Web deployment (Render, Vercel) |
| `yarn build:mobile` | Static export | `out/` | Bearer tokens | Capacitor iOS/Android |

The switch is controlled by `next.config.mjs`:

```js
const isMobile = process.env.NEXT_BUILD_MODE === "mobile";
// When mobile: output: "export", images: { unoptimized: true }
```

`capacitor.config.ts` points `webDir` at `out/`, so `npx cap sync` copies the static export into the native projects.

---

## Prerequisites

| Tool | Version | Required For |
|------|---------|--------------|
| Node.js | 20+ | Building the frontend |
| Yarn | 1.x | Package management |
| macOS | 13+ | iOS builds (Xcode requires macOS) |
| Xcode | 15+ | iOS builds, simulator testing |
| CocoaPods | Latest | iOS native dependency management |
| Android Studio | Latest | Android builds, emulator testing |
| Java JDK | 17 | Android Gradle builds |
| Python | 3.11+ | Backend (Django) |
| Poetry | Latest | Backend dependency management |

**Install CocoaPods (if not already installed):**
```bash
sudo gem install cocoapods
```

---

## Initial Setup (First Time)

After cloning the repo and checking out this branch:

```bash
# 1. Install frontend dependencies
cd frontend && yarn install

# 2. Install iOS pods (requires macOS + Xcode)
cd ios/App && pod install && cd ../..

# 3. Build the mobile static export
yarn build:mobile

# 4. Sync web assets to native projects
npx cap sync

# 5. Install backend dependencies
cd ../backend && poetry install

# 6. Run migrations (includes the new notifications app)
python manage.py migrate
```

---

## Firebase Setup

Firebase Cloud Messaging (FCM) powers push notifications on both iOS and Android.

### Step 1: Create Firebase project

1. Go to [console.firebase.google.com](https://console.firebase.google.com)
2. Click **Add project**, name it (e.g. "MenuChat")
3. Disable Google Analytics if not needed
4. Click **Create project**

### Step 2: Add iOS app

1. In Firebase console → **Project settings** → **General** → **Your apps** → **Add app** → iOS
2. **Bundle ID:** `com.menuchat.qrordering`
3. **App nickname:** MenuChat iOS
4. Click **Register app**
5. Download `GoogleService-Info.plist`
6. Place it at `frontend/ios/App/App/GoogleService-Info.plist`
7. In Xcode, drag the file into the App group — make sure "Copy items if needed" is checked and the App target is selected

### Step 3: Add Android app

1. In Firebase console → **Add app** → Android
2. **Package name:** `com.menuchat.qrordering`
3. **App nickname:** MenuChat Android
4. Click **Register app**
5. Download `google-services.json`
6. Place it at `frontend/android/app/google-services.json`

### Step 4: Configure iOS push (APNs)

1. Go to [Apple Developer portal](https://developer.apple.com/account) → **Certificates, Identifiers & Profiles** → **Keys**
2. Click **+** to create a new key
3. Name it (e.g. "MenuChat Push")
4. Check **Apple Push Notifications service (APNs)**
5. Click **Continue** → **Register**
6. Download the `.p8` key file (save it securely — you can only download it once)
7. Note the **Key ID** and your **Team ID** (visible at the top of the developer portal)
8. In Firebase console → **Project settings** → **Cloud Messaging** → **Apple app configuration**
9. Upload the `.p8` file, enter the Key ID and Team ID

### Step 5: Generate backend service account key

1. Firebase console → **Project settings** → **Service accounts**
2. Click **Generate new private key**
3. Download the JSON file
4. Set the **entire JSON contents** (as a single-line string) as the `FIREBASE_CREDENTIALS_JSON` environment variable on your backend server

```bash
# Example (for local development):
export FIREBASE_CREDENTIALS_JSON='{"type":"service_account","project_id":"menuchat-xxxxx",...}'
```

For production (e.g. Render), add this as an environment variable in the dashboard.

---

## Google OAuth Setup (Native)

Web Google Sign-In uses Google Identity Services (GIS) loaded via `<script>`. On native, the `@codetrix-studio/capacitor-google-auth` plugin handles sign-in natively.

### Step 1: Create OAuth 2.0 credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Credentials**
2. You need **three** OAuth 2.0 Client IDs:

| Type | Used By |
|------|---------|
| **Web application** | Web frontend (GIS), backend token verification |
| **iOS** | Native iOS Google Sign-In |
| **Android** | Native Android Google Sign-In |

3. For the **Web** client: set authorized JavaScript origins to your frontend domain and `http://localhost:3001`. Set the client ID as `NEXT_PUBLIC_GOOGLE_CLIENT_ID`.

4. For the **iOS** client:
   - Bundle ID: `com.menuchat.qrordering`
   - Add the **reversed client ID** (e.g. `com.googleusercontent.apps.XXXXX`) as a URL scheme in `frontend/ios/App/App/Info.plist`

5. For the **Android** client:
   - Package name: `com.menuchat.qrordering`
   - SHA-1 fingerprint: Run `cd frontend/android && ./gradlew signingReport` to get the debug fingerprint. For release, use the keystore fingerprint.

### Step 2: Configure in Capacitor

The `serverClientId` in `frontend/capacitor.config.ts` must be the **Web** client ID (not the iOS/Android one). This is used for backend token verification:

```ts
plugins: {
  GoogleAuth: {
    scopes: ["profile", "email"],
    serverClientId: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "",
    forceCodeForRefreshToken: true,
  },
}
```

Both the web and native flows send an `id_token` to the backend's `/api/auth/google/` endpoint, which verifies it against the Web client ID. The native plugins handle the platform-specific OAuth flows automatically.

---

## Apple Sign-In Setup (Native)

Apple Sign-In works on iOS only (the button is hidden on Android). On web, it uses the Apple JS SDK. On native iOS, it uses `@capacitor-community/apple-sign-in` which delegates to the system-level Sign in with Apple.

### Step 1: Configure in Apple Developer portal

1. Go to [developer.apple.com](https://developer.apple.com/account) → **Certificates, Identifiers & Profiles** → **Identifiers**
2. Select your App ID (`com.menuchat.qrordering`)
3. Enable **Sign in with Apple** capability
4. If you also need web Apple Sign-In, create a **Services ID** and configure the return URL

### Step 2: Enable in Xcode

1. Open `frontend/ios/App/App.xcworkspace` in Xcode
2. Select the App target → **Signing & Capabilities**
3. Click **+ Capability** → **Sign in with Apple**

No additional code changes needed — the plugin handles everything via the system dialog.

---

## App Icons and Splash Screens

### Step 1: Prepare source images

| File | Size | Notes |
|------|------|-------|
| `frontend/resources/icon.png` | 1024x1024 | No transparency, no rounded corners (iOS adds rounding) |
| `frontend/resources/splash.png` | 2732x2732 | Center the logo; outer area may be cropped on smaller screens |

### Step 2: Generate all sizes

```bash
cd frontend && npx @capacitor/assets generate
```

This generates all required icon sizes (20x20 through 1024x1024 for iOS, mdpi through xxxhdpi for Android) and splash screen variants, placing them in the correct native project directories.

### Step 3: Verify

- iOS: Check `frontend/ios/App/App/Assets.xcassets/AppIcon.appiconset/`
- Android: Check `frontend/android/app/src/main/res/mipmap-*/`

---

## Building for iOS

### Development build (simulator)

```bash
cd frontend
yarn build:mobile        # Static export → out/
npx cap sync             # Copy to native projects
npx cap open ios         # Opens Xcode
```

In Xcode:
1. Select an iPhone simulator from the device dropdown
2. Press **Cmd+R** to build and run
3. The app should load showing the MenuChat home page

### Release build (App Store)

1. **Prerequisites:**
   - Apple Developer account enrolled ($99/year)
   - App record created in [App Store Connect](https://appstoreconnect.apple.com)
   - `GoogleService-Info.plist` added to the Xcode project
   - Push Notifications and Sign in with Apple capabilities enabled

2. **In Xcode:**
   - Set the **Team** under Signing & Capabilities (your Apple Developer team)
   - Ensure **Bundle Identifier** is `com.menuchat.qrordering`
   - Set the **Version** and **Build** numbers
   - Add required `Info.plist` privacy descriptions:
     - `NSCameraUsageDescription` — "MenuChat uses your camera to scan QR codes at restaurants"
     - `NSUserTrackingUsageDescription` — (only if using ATT)
   - Add **Associated Domains** capability with `applinks:yourdomain.com` (for deep links)

3. **Archive and upload:**
   - Select **Any iOS Device** as the build target
   - **Product** → **Archive**
   - In the Organizer window, click **Distribute App**
   - Select **App Store Connect** → **Upload**
   - Follow the prompts to upload

4. **TestFlight:**
   - In App Store Connect → **TestFlight** → select the build
   - Add internal or external testers
   - External testing requires Apple review (usually < 24 hours)

---

## Building for Android

### Development build (emulator)

```bash
cd frontend
yarn build:mobile        # Static export → out/
npx cap sync             # Copy to native projects
npx cap open android     # Opens Android Studio
```

In Android Studio:
1. Wait for Gradle sync to complete
2. Select an emulator or connected device
3. Click the **Run** button (green triangle)

### Release build (Play Store)

1. **Prerequisites:**
   - Google Play Developer account ($25 one-time)
   - App record created in [Google Play Console](https://play.google.com/console)
   - `google-services.json` placed in `frontend/android/app/`

2. **Create a signing keystore** (one time):
   ```bash
   keytool -genkey -v \
     -keystore menuchat-release.keystore \
     -alias menuchat \
     -keyalg RSA \
     -keysize 2048 \
     -validity 10000
   ```
   Store the keystore file and password securely. You need them for every release.

3. **Configure signing** in `frontend/android/app/build.gradle`:
   ```groovy
   android {
       signingConfigs {
           release {
               storeFile file("menuchat-release.keystore")
               storePassword System.getenv("KEYSTORE_PASSWORD")
               keyAlias "menuchat"
               keyPassword System.getenv("KEY_PASSWORD")
           }
       }
       buildTypes {
           release {
               signingConfig signingConfigs.release
               minifyEnabled true
               proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
           }
       }
   }
   ```

4. **Generate signed AAB:**
   - In Android Studio: **Build** → **Generate Signed Bundle / APK**
   - Select **Android App Bundle**
   - Select or create your keystore
   - Choose **release** build variant
   - The `.aab` file will be in `frontend/android/app/build/outputs/bundle/release/`

5. **Upload to Play Store:**
   - Google Play Console → your app → **Production** → **Create new release**
   - Upload the `.aab` file
   - Add release notes
   - Submit for review

---

## Push Notifications

### How it works

1. **Registration:** When the native app starts, `usePushNotifications` hook requests permission and registers with FCM. The returned device token is sent to `POST /api/devices/register/` and stored in the `DeviceToken` model.

2. **Sending:** When orders are created or their status changes, `broadcast.py` calls `send_push_notification()` which uses the Firebase Admin SDK to send via FCM.

3. **Token lifecycle:** If FCM returns `UnregisteredError` (device uninstalled the app, token expired), the token is automatically deactivated in the database.

### Push notification triggers

| Event | Recipient | Title |
|-------|-----------|-------|
| New order placed | Restaurant owner | "New Order" |
| Order status → ready | Customer (user or anonymous order) | "Order Ready!" |

### Testing push notifications locally

1. Set `FIREBASE_CREDENTIALS_JSON` env var on the backend
2. Run the backend and place a test order
3. The push will be sent to any registered device tokens for the restaurant owner

Note: Push notifications don't work on iOS simulators. Use a physical device or TestFlight.

---

## Deep Linking

Deep links allow URLs like `https://yourdomain.com/order/my-restaurant/table-5` to open directly in the native app.

### Frontend handling

The `DeepLinkHandler` component (rendered by `NativeInitializer`) listens for `appUrlOpen` events. When a deep link is received, it extracts the path and uses Next.js client-side routing to navigate.

### iOS setup (Universal Links)

1. In Xcode → **Signing & Capabilities** → **Associated Domains** → add `applinks:yourdomain.com`

2. Host `apple-app-site-association` on your web server (no file extension, served as JSON):

   **URL:** `https://yourdomain.com/.well-known/apple-app-site-association`

   ```json
   {
     "applinks": {
       "apps": [],
       "details": [
         {
           "appID": "TEAM_ID.com.menuchat.qrordering",
           "paths": ["/order/*"]
         }
       ]
     }
   }
   ```

   Replace `TEAM_ID` with your Apple Developer Team ID.

   Requirements:
   - Served over HTTPS (no redirects)
   - `Content-Type: application/json`
   - No authentication required

### Android setup (App Links)

1. The `AndroidManifest.xml` already has the intent filter for `https://yourdomain.com/order/*`. Update the `android:host` to your actual domain.

2. Host `assetlinks.json` on your web server:

   **URL:** `https://yourdomain.com/.well-known/assetlinks.json`

   ```json
   [{
     "relation": ["delegate_permission/common.handle_all_urls"],
     "target": {
       "namespace": "android_app",
       "package_name": "com.menuchat.qrordering",
       "sha256_cert_fingerprints": ["YOUR_SHA256_FINGERPRINT"]
     }
   }]
   ```

   Get the SHA-256 fingerprint of your signing certificate:
   ```bash
   keytool -list -v -keystore menuchat-release.keystore | grep SHA256
   ```

### Deploying the well-known files

If using Render/Vercel for the web backend, add a static route or serverless function to serve these files at `/.well-known/`. Alternatively, use your CDN or reverse proxy to serve them.

---

## Environment Variables Reference

### Backend

| Variable | Required | Description |
|----------|----------|-------------|
| `FIREBASE_CREDENTIALS_JSON` | For push notifications | Firebase service account key as a JSON string |
| `DJANGO_SECRET_KEY` | Yes | Django secret key |
| `POSTGRES_*` | Yes | Database connection settings |
| `REDIS_URL` | Yes | Redis for Channels (WebSocket) and Celery |
| `GOOGLE_CLIENT_ID` | For Google auth | Google OAuth Web client ID (backend verification) |
| `APPLE_CLIENT_ID` | For Apple auth | Apple Sign-In Service ID |

### Frontend (build-time, prefix with `NEXT_PUBLIC_`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API URL (e.g. `https://api.menuchat.app`) |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | For Google auth | Google OAuth Web client ID (same as backend) |
| `NEXT_PUBLIC_APPLE_CLIENT_ID` | For Apple auth | Apple Sign-In Service ID |
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` | For maps | Google Maps JavaScript API key |
| `NEXT_BUILD_MODE` | For mobile build | Set to `mobile` by `yarn build:mobile` |

### Native-only (configured in code)

| Location | Setting | Description |
|----------|---------|-------------|
| `capacitor.config.ts` | `plugins.GoogleAuth.serverClientId` | Google OAuth Web client ID |
| `ios/App/App/Info.plist` | URL schemes | Reversed Google client ID for iOS OAuth redirect |
| `android/app/google-services.json` | Firebase config | Auto-configures FCM and Google Auth on Android |
| `ios/App/App/GoogleService-Info.plist` | Firebase config | Auto-configures FCM and Google Auth on iOS |

---

## Development Workflow

### Web development (unchanged)

```bash
cd frontend && yarn dev          # Next.js dev server on port 3001
cd backend && python manage.py runserver 0.0.0.0:5005
```

### Mobile development

```bash
# Build static export and sync to native projects
cd frontend
yarn build:mobile
npx cap sync

# Open in IDE and run on simulator/device
npx cap open ios       # → Xcode
npx cap open android   # → Android Studio
```

### Quick iteration (code changes only, no new dependencies)

```bash
# After changing frontend code:
yarn build:mobile && npx cap sync

# Then in Xcode/Android Studio, just hit Run again
```

### After installing new Capacitor plugins

```bash
yarn add @capacitor/some-plugin
npx cap sync                    # Copies web assets AND updates native plugins

# iOS: may need to re-run pod install
cd ios/App && pod install && cd ../..
```

---

## How Auth Works on Native vs Web

### Web flow
1. User logs in → backend sets httpOnly `access_token` and `refresh_token` cookies
2. `apiFetch` includes `credentials: "include"` → cookies are sent automatically
3. CSRF token is read from the `csrftoken` cookie and sent as `X-CSRFToken` header
4. On 401, `tryRefresh()` sends `POST /api/auth/refresh/` with cookies

### Native flow
1. User logs in → backend returns `access_token` and `refresh_token` in the response body (cookies are also set but ignored by native)
2. Tokens are saved to `@capacitor/preferences` via `setTokens()`
3. `apiFetch` detects `isNativePlatform()` → reads token from storage → sends `Authorization: Bearer <token>` header
4. No CSRF needed (not using cookies)
5. No `credentials: "include"` (not using cookies)
6. On 401, `tryRefresh()` sends the refresh token in the request body → saves new tokens on success

### Social auth
- **Web:** Google Identity Services / Apple JS SDK loaded via `<Script>` tags
- **Native:** `@codetrix-studio/capacitor-google-auth` and `@capacitor-community/apple-sign-in` plugins
- The `SocialLoginButtons` component detects the platform and uses the appropriate flow
- Both flows produce an `id_token` that is sent to the same backend endpoint

---

## Key Files and Their Purpose

### Frontend — Capacitor infrastructure

| File | Purpose |
|------|---------|
| `capacitor.config.ts` | Capacitor configuration (app ID, web dir, plugin settings) |
| `next.config.mjs` | Dual build mode — conditional `output: 'export'` |
| `src/lib/native.ts` | `isNativePlatform()` and `getPlatform()` helpers |
| `src/lib/token-storage.ts` | Secure token storage via `@capacitor/preferences` |
| `src/components/NativeInitializer.tsx` | Initializes push notifications, status bar, deep links |
| `src/components/DeepLinkHandler.tsx` | Handles `appUrlOpen` events for deep linking |
| `src/components/WebOnlyScripts.tsx` | Conditionally loads Google/Apple OAuth web SDKs |
| `src/hooks/use-push-notifications.ts` | Registers for push and sends FCM token to backend |
| `src/hooks/use-native-camera.ts` | Native QR code scanning via MLKit |
| `src/hooks/use-websocket.ts` | WebSocket with app lifecycle reconnection |
| `public/404.html` | SPA fallback for Capacitor (deep link routing) |

### Frontend — Modified for native support

| File | Change |
|------|--------|
| `src/lib/api.ts` | Bearer auth on native, cookies on web |
| `src/stores/auth-store.ts` | Save/clear tokens on native login/logout |
| `src/components/SocialLoginButtons.tsx` | Native Google/Apple auth plugins |
| `src/app/layout.tsx` | `NativeInitializer` + `WebOnlyScripts` |
| `src/app/globals.css` | `env(safe-area-inset-*)` padding |
| `src/app/page.tsx` | SPA fallback redirect for deep links |
| All dynamic route `page.tsx` files | Server wrapper + `generateStaticParams` for static export |

### Backend — New notifications app

| File | Purpose |
|------|---------|
| `notifications/models.py` | `DeviceToken` model (FCM tokens linked to users or orders) |
| `notifications/views.py` | `DeviceRegisterView` — register/update device tokens |
| `notifications/services.py` | `send_push_notification()` — Firebase push delivery |
| `notifications/serializers.py` | Input validation for device registration |
| `notifications/urls.py` | `/api/devices/register/` route |

### Backend — Modified for native support

| File | Change |
|------|--------|
| `accounts/services.py` | `set_auth_cookies` now also injects tokens into response body |
| `accounts/views.py` | `RefreshView` accepts token from body; `WsTokenView` checks Authorization header |
| `orders/broadcast.py` | Push notifications on new order and order ready |
| `config/settings.py` | `FIREBASE_CREDENTIALS` setting, `notifications` in INSTALLED_APPS |
| `config/urls.py` | Include `notifications.urls` |

---

## Troubleshooting

### Build issues

| Problem | Solution |
|---------|----------|
| `yarn build:mobile` fails with type errors | Run `yarn install` to ensure all types are installed. Check that `@capacitor/cli` matches `@capacitor/core` version (both should be v6). |
| `npx cap sync` fails on iOS | Run `cd ios/App && pod install --repo-update`. Ensure CocoaPods is installed. |
| `npx cap sync` warns about missing plugins | Run `npx cap sync` again after installing the plugin with `yarn add`. |
| Xcode build fails with signing errors | Select your development team in Signing & Capabilities. Ensure the bundle ID matches. |
| Android Gradle sync fails | File → Sync Project with Gradle Files. Ensure `google-services.json` is present. |

### Runtime issues

| Problem | Solution |
|---------|----------|
| App shows blank white screen | Check the browser console in Xcode (Safari → Develop → Simulator) or Android Studio (chrome://inspect). Usually a JS error. |
| Push notifications not received (iOS) | Ensure the APNs key is uploaded to Firebase. Push doesn't work on simulators — use a real device. |
| Push notifications not received (Android) | Ensure `google-services.json` is in `android/app/`. Check logcat for FCM registration errors. |
| Google Sign-In fails on native | Verify the `serverClientId` in `capacitor.config.ts` matches your Web OAuth client ID. For iOS, ensure the reversed client ID URL scheme is in `Info.plist`. |
| Apple Sign-In button not showing | Apple Sign-In only appears on iOS. On Android and web, it uses the JS SDK. |
| Deep links not opening the app | Verify the `apple-app-site-association` / `assetlinks.json` are hosted correctly. Test with: `adb shell am start -a android.intent.action.VIEW -d "https://yourdomain.com/order/test"` |
| WebSocket disconnects on background/foreground | This is handled automatically — the `useWebSocket` hook reconnects when the app returns to foreground via the `@capacitor/app` lifecycle listener. |
| 401 errors on native | Check that tokens are being stored — `@capacitor/preferences` requires the native platform. In the browser, `isNativePlatform()` returns false, so cookie auth is used instead. |
| CORS errors on native | The backend's `CORS_ALLOW_ALL_ORIGINS = True` in debug mode should handle this. In production, add the Capacitor origin (`capacitor://localhost` and `https://app.localhost`) to `CORS_ALLOWED_ORIGINS`. |

### Debugging tools

- **iOS:** Safari → Develop → [Your Simulator] → inspect the web view
- **Android:** Open `chrome://inspect` in Chrome desktop → find your device/emulator
- **Network requests:** Both Safari and Chrome dev tools show network requests from the web view
- **Push notification logs:** Check `adb logcat | grep FCM` (Android) or Xcode console (iOS)
