# Mobile Deployment Guide

## Prerequisites

- **macOS** with Xcode 15+ (for iOS builds)
- **Android Studio** (for Android builds)
- **Node.js 20+** and **Yarn**
- **CocoaPods** (`sudo gem install cocoapods`)

## Developer Account Setup

### Apple Developer Program
- Enroll at [developer.apple.com](https://developer.apple.com)
- $99/year
- Required for TestFlight and App Store distribution

### Google Play Developer
- Register at [play.google.com/console](https://play.google.com/console)
- $25 one-time fee
- Required for Play Store distribution

## Firebase Setup

1. Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com)
2. **Add iOS app:**
   - Bundle ID: `com.menuchat.qrordering`
   - Download `GoogleService-Info.plist`
   - Place in `frontend/ios/App/App/`
3. **Add Android app:**
   - Package name: `com.menuchat.qrordering`
   - Download `google-services.json`
   - Place in `frontend/android/app/`
4. **iOS Push (APNs):**
   - In Apple Developer portal, create an APNs authentication key
   - Upload the `.p8` key file to Firebase > Project Settings > Cloud Messaging > iOS
5. **Backend service account:**
   - Firebase > Project Settings > Service Accounts > Generate New Private Key
   - Set the JSON contents as the `FIREBASE_CREDENTIALS_JSON` environment variable on the backend

## App Icons & Splash Screens

Place source images:
- `frontend/resources/icon.png` (1024x1024, no transparency for iOS)
- `frontend/resources/splash.png` (2732x2732)

Generate all platform-specific sizes:
```bash
cd frontend && npx @capacitor/assets generate
```

## Building for iOS

### Build and sync
```bash
cd frontend
yarn build:mobile
npx cap sync
npx cap open ios
```

### In Xcode
1. Select your development team under **Signing & Capabilities**
2. Add `GoogleService-Info.plist` to the App target (drag into the project navigator)
3. Add privacy descriptions to `Info.plist`:
   - `NSCameraUsageDescription` — "We need camera access to scan QR codes"
   - `NSLocationWhenInUseUsageDescription` — (if using location features)
4. Add **Push Notifications** capability
5. Add **Associated Domains** capability with `applinks:yourdomain.com`
6. Select **Product > Archive** to create a release build
7. Upload to App Store Connect via the Organizer

### TestFlight
- In App Store Connect, add the build to a TestFlight group
- Invite testers via email

## Building for Android

### Build and sync
```bash
cd frontend
yarn build:mobile
npx cap sync
npx cap open android
```

### In Android Studio
1. Add `google-services.json` to `android/app/`
2. Create a signing keystore:
   ```bash
   keytool -genkey -v -keystore menuchat-release.keystore -alias menuchat -keyalg RSA -keysize 2048 -validity 10000
   ```
3. Configure signing in `android/app/build.gradle`:
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
           }
       }
   }
   ```
4. Generate signed AAB: **Build > Generate Signed Bundle/APK**
5. Upload to Google Play Console

## Deep Linking Setup

### iOS (Universal Links)
Host `apple-app-site-association` at `https://yourdomain.com/.well-known/apple-app-site-association`:

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

Must be served with `Content-Type: application/json` over HTTPS (no redirect).

### Android (App Links)
Host `assetlinks.json` at `https://yourdomain.com/.well-known/assetlinks.json`:

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

Get the fingerprint:
```bash
keytool -list -v -keystore menuchat-release.keystore | grep SHA256
```

## Environment Variables

### Backend
| Variable | Description |
|----------|-------------|
| `FIREBASE_CREDENTIALS_JSON` | Firebase service account key (JSON string) |

### Frontend (build-time)
| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google OAuth client ID (for native Google Sign-In) |
| `NEXT_PUBLIC_APPLE_CLIENT_ID` | Apple Sign-In service ID |
| `NEXT_PUBLIC_API_URL` | Backend API URL |
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` | Google Maps API key |

### Native Config
Google Auth client IDs are configured in `frontend/capacitor.config.ts` under `plugins.GoogleAuth.serverClientId`.

## Development Workflow

```bash
# Web development (normal)
cd frontend && yarn dev

# Mobile build + preview
cd frontend && yarn build:mobile && npx cap sync

# Open in IDE
npx cap open ios      # Opens Xcode
npx cap open android  # Opens Android Studio
```

## Troubleshooting

- **iOS pod install fails:** Run `cd ios/App && pod install --repo-update`
- **Android build fails on signing:** Ensure keystore path is correct and passwords match
- **Push notifications not received:** Verify APNs key is uploaded to Firebase and `GoogleService-Info.plist` / `google-services.json` are in the correct locations
- **Deep links not working:** Verify the `apple-app-site-association` / `assetlinks.json` files are accessible at `/.well-known/` on your domain
