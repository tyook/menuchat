"use client";

import { useCallback, useState } from "react";
import { isNativePlatform } from "@/lib/native";

export function useNativeCamera() {
  const [isScanning, setIsScanning] = useState(false);
  const isAvailable = isNativePlatform();

  const scan = useCallback(async (): Promise<string | null> => {
    if (!isNativePlatform()) return null;

    const { BarcodeScanner, BarcodeFormat } = await import(
      "@capacitor-mlkit/barcode-scanning"
    );

    const permission = await BarcodeScanner.requestPermissions();
    if (permission.camera !== "granted") return null;

    setIsScanning(true);
    try {
      const { barcodes } = await BarcodeScanner.scan({
        formats: [BarcodeFormat.QrCode],
      });

      if (barcodes.length > 0 && barcodes[0].rawValue) {
        return barcodes[0].rawValue;
      }
      return null;
    } finally {
      setIsScanning(false);
    }
  }, []);

  return { scan, isAvailable, isScanning };
}
