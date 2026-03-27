"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { MenuUploadModal } from "@/components/menu-upload-modal";
import { Upload } from "lucide-react";

interface MenuUploadStepProps {
  slug: string;
  onComplete: () => void;
  onSkip: () => void;
}

export function MenuUploadStep({ slug, onComplete, onSkip }: MenuUploadStepProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [hasUploaded, setHasUploaded] = useState(false);

  const handleModalChange = (open: boolean) => {
    setModalOpen(open);
    if (!open && modalOpen) {
      // Modal was just closed -- assume upload happened if it was open
      setHasUploaded(true);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Upload Your Menu</h1>
        <p className="text-muted-foreground mt-1">
          Upload photos of your menu and we will digitize it automatically using AI.
        </p>
      </div>

      <div className="flex flex-col items-center gap-4 rounded-lg border-2 border-dashed border-muted p-8">
        <Upload className="h-10 w-10 text-muted-foreground" />
        <p className="text-sm text-muted-foreground text-center">
          Take photos of your paper menu or upload existing images.
          We support JPEG, PNG, and HEIC formats.
        </p>
        <Button onClick={() => setModalOpen(true)}>
          Upload Menu Photos
        </Button>
      </div>

      <div className="flex gap-3 pt-2">
        {hasUploaded ? (
          <Button onClick={onComplete} className="flex-1">
            Continue
          </Button>
        ) : (
          <Button variant="ghost" onClick={onSkip} className="flex-1">
            Skip for now
          </Button>
        )}
      </div>

      <MenuUploadModal
        slug={slug}
        open={modalOpen}
        onOpenChange={handleModalChange}
        hasExistingMenu={false}
      />
    </div>
  );
}
