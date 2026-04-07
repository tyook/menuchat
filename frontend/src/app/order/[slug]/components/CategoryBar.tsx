"use client";

import { useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";

interface CategoryBarProps {
  categories: { id: number; name: string }[];
  activeCategoryId: number | null;
  onCategoryClick: (categoryId: number) => void;
}

export function CategoryBar({
  categories,
  activeCategoryId,
  onCategoryClick,
}: CategoryBarProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pillRefs = useRef<Map<number, HTMLButtonElement>>(new Map());

  // Scroll the active pill into view
  useEffect(() => {
    if (activeCategoryId == null) return;
    const pill = pillRefs.current.get(activeCategoryId);
    if (pill && scrollRef.current) {
      pill.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "center",
      });
    }
  }, [activeCategoryId]);

  const setPillRef = useCallback(
    (id: number) => (el: HTMLButtonElement | null) => {
      if (el) pillRefs.current.set(id, el);
      else pillRefs.current.delete(id);
    },
    [],
  );

  return (
    <div
      ref={scrollRef}
      className="flex gap-2 overflow-x-auto scrollbar-hide py-2 px-4 -mx-4"
      style={{ WebkitOverflowScrolling: "touch", scrollSnapType: "x mandatory" }}
    >
      {categories.map((cat) => (
        <button
          key={cat.id}
          ref={setPillRef(cat.id)}
          onClick={() => onCategoryClick(cat.id)}
          className={cn(
            "shrink-0 rounded-full px-4 py-2 text-sm font-medium transition-colors min-h-[36px]",
            "snap-start",
            activeCategoryId === cat.id
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground hover:bg-muted/80",
          )}
        >
          {cat.name}
        </button>
      ))}
    </div>
  );
}
