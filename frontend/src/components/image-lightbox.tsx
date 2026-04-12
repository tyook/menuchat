"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";

interface ImageLightboxProps {
  src: string;
  alt: string;
  className?: string;
}

export function ImageLightbox({ src, alt, className }: ImageLightboxProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <img
        src={src}
        alt={alt}
        loading="lazy"
        className={`${className} cursor-pointer`}
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
      />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-sm p-2 bg-transparent border-none shadow-none [&>button]:text-white">
          <img
            src={src}
            alt={alt}
            className="w-full rounded-xl object-contain max-h-[70vh]"
          />
        </DialogContent>
      </Dialog>
    </>
  );
}
