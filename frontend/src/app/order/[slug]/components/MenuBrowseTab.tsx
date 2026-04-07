"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { CategoryBar } from "./CategoryBar";
import { MenuItemCard } from "./MenuItemCard";
import type { MenuCategory } from "@/types";

interface MenuBrowseTabProps {
  categories: MenuCategory[];
}

export function MenuBrowseTab({ categories }: MenuBrowseTabProps) {
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(
    categories[0]?.id ?? null,
  );
  const [expandedItemId, setExpandedItemId] = useState<number | null>(null);
  const suppressObserverRef = useRef(false);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const categoryRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const suppressTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const setCategoryRef = useCallback(
    (id: number) => (el: HTMLDivElement | null) => {
      if (el) categoryRefs.current.set(id, el);
      else categoryRefs.current.delete(id);
    },
    [],
  );

  // IntersectionObserver to track which category is in view
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container || categories.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (suppressObserverRef.current) return;
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const id = Number(entry.target.getAttribute("data-category-id"));
            if (!isNaN(id)) setActiveCategoryId(id);
          }
        }
      },
      {
        root: container,
        rootMargin: "-20% 0px -70% 0px",
        threshold: 0,
      },
    );

    categoryRefs.current.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, [categories]);

  const handleCategoryClick = (categoryId: number) => {
    const el = categoryRefs.current.get(categoryId);
    if (!el) return;

    // Suppress observer during programmatic scroll
    suppressObserverRef.current = true;
    setActiveCategoryId(categoryId);

    el.scrollIntoView({ behavior: "smooth", block: "start" });

    clearTimeout(suppressTimerRef.current);
    suppressTimerRef.current = setTimeout(() => {
      suppressObserverRef.current = false;
    }, 800);
  };

  const handleToggleExpand = (itemId: number) => {
    setExpandedItemId((prev) => (prev === itemId ? null : itemId));
  };

  if (categories.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-sm text-muted-foreground">No menu items available.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Sticky category bar */}
      <div className="sticky top-0 z-10 bg-background/95 backdrop-blur-sm border-b border-border/50">
        <CategoryBar
          categories={categories.map((c) => ({ id: c.id, name: c.name }))}
          activeCategoryId={activeCategoryId}
          onCategoryClick={handleCategoryClick}
        />
      </div>

      {/* Scrollable menu items */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-4 pb-24"
        style={{ WebkitOverflowScrolling: "touch" }}
      >
        {categories.map((category) => (
          <div
            key={category.id}
            ref={setCategoryRef(category.id)}
            data-category-id={category.id}
            className="pt-4"
          >
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
              {category.name}
            </h3>
            <div className="space-y-2">
              {category.items.map((item) => (
                <MenuItemCard
                  key={item.id}
                  item={item}
                  isExpanded={expandedItemId === item.id}
                  onToggleExpand={() => handleToggleExpand(item.id)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
