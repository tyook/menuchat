"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useProfile, useUpdateProfile } from "@/hooks/use-profile";
import { SPEECH_LANGUAGES } from "@/lib/constants";
import { X } from "lucide-react";

const PREDEFINED_DIETARY_PREFERENCES = [
  "Vegetarian",
  "Vegan",
  "Halal",
  "Kosher",
  "Gluten-Free",
  "Pescatarian",
  "Dairy-Free",
];

const PREDEFINED_ALLERGIES = [
  "Peanuts",
  "Tree Nuts",
  "Dairy",
  "Eggs",
  "Shellfish",
  "Soy",
  "Wheat",
  "Fish",
];

interface PreferencesStepProps {
  onNext: () => void;
  onSkip: () => void;
}

export function PreferencesStep({ onNext, onSkip }: PreferencesStepProps) {
  const { data: profile } = useProfile();
  const updateProfile = useUpdateProfile();

  const [dietaryPreferences, setDietaryPreferences] = useState<string[]>([]);
  const [allergies, setAllergies] = useState<string[]>([]);
  const [preferredLanguage, setPreferredLanguage] = useState("en-US");
  const [customDietaryInput, setCustomDietaryInput] = useState("");
  const [customAllergyInput, setCustomAllergyInput] = useState("");

  useEffect(() => {
    if (profile) {
      setDietaryPreferences(profile.dietary_preferences || []);
      setAllergies(profile.allergies || []);
      setPreferredLanguage(profile.preferred_language || "en-US");
    }
  }, [profile]);

  const toggleDietaryPreference = (pref: string) => {
    setDietaryPreferences((prev) =>
      prev.includes(pref) ? prev.filter((p) => p !== pref) : [...prev, pref]
    );
  };

  const addCustomDietaryPreference = () => {
    const trimmed = customDietaryInput.trim();
    if (trimmed && !dietaryPreferences.includes(trimmed)) {
      setDietaryPreferences([...dietaryPreferences, trimmed]);
      setCustomDietaryInput("");
    }
  };

  const removeDietaryPreference = (pref: string) => {
    setDietaryPreferences(dietaryPreferences.filter((p) => p !== pref));
  };

  const toggleAllergy = (allergy: string) => {
    setAllergies((prev) =>
      prev.includes(allergy) ? prev.filter((a) => a !== allergy) : [...prev, allergy]
    );
  };

  const addCustomAllergy = () => {
    const trimmed = customAllergyInput.trim();
    if (trimmed && !allergies.includes(trimmed)) {
      setAllergies([...allergies, trimmed]);
      setCustomAllergyInput("");
    }
  };

  const removeAllergy = (allergy: string) => {
    setAllergies(allergies.filter((a) => a !== allergy));
  };

  const handleSave = () => {
    updateProfile.mutate(
      {
        dietary_preferences: dietaryPreferences,
        allergies,
        preferred_language: preferredLanguage,
      },
      { onSuccess: onNext }
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Your Preferences</h1>
        <p className="text-muted-foreground mt-1">
          Help us personalize your experience with dietary preferences and language settings.
        </p>
      </div>

      {/* Dietary Preferences */}
      <div className="glass-card rounded-2xl p-4 space-y-3">
        <h2 className="text-foreground font-medium text-sm">Dietary Restrictions</h2>
        <div className="flex flex-wrap gap-2">
          {PREDEFINED_DIETARY_PREFERENCES.map((pref) => (
            <Badge
              key={pref}
              variant={dietaryPreferences.includes(pref) ? "default" : "outline"}
              className="cursor-pointer"
              onClick={() => toggleDietaryPreference(pref)}
            >
              {pref}
            </Badge>
          ))}
        </div>
        {dietaryPreferences.filter(
          (p) => !PREDEFINED_DIETARY_PREFERENCES.includes(p)
        ).length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2 border-t">
            {dietaryPreferences
              .filter((p) => !PREDEFINED_DIETARY_PREFERENCES.includes(p))
              .map((pref) => (
                <Badge key={pref} variant="secondary" className="gap-1">
                  {pref}
                  <X
                    className="h-3 w-3 cursor-pointer"
                    onClick={() => removeDietaryPreference(pref)}
                  />
                </Badge>
              ))}
          </div>
        )}
        <div className="flex gap-2">
          <Input
            value={customDietaryInput}
            onChange={(e) => setCustomDietaryInput(e.target.value)}
            placeholder="Add custom preference..."
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addCustomDietaryPreference();
              }
            }}
          />
          <Button
            type="button"
            variant="outline"
            onClick={addCustomDietaryPreference}
            disabled={!customDietaryInput.trim()}
          >
            Add
          </Button>
        </div>
      </div>

      {/* Allergies */}
      <div className="glass-card rounded-2xl p-4 space-y-3">
        <h2 className="text-foreground font-medium text-sm">Allergies</h2>
        <div className="flex flex-wrap gap-2">
          {PREDEFINED_ALLERGIES.map((allergy) => (
            <Badge
              key={allergy}
              variant={allergies.includes(allergy) ? "default" : "outline"}
              className="cursor-pointer"
              onClick={() => toggleAllergy(allergy)}
            >
              {allergy}
            </Badge>
          ))}
        </div>
        {allergies.filter((a) => !PREDEFINED_ALLERGIES.includes(a)).length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2 border-t">
            {allergies
              .filter((a) => !PREDEFINED_ALLERGIES.includes(a))
              .map((allergy) => (
                <Badge key={allergy} variant="secondary" className="gap-1">
                  {allergy}
                  <X
                    className="h-3 w-3 cursor-pointer"
                    onClick={() => removeAllergy(allergy)}
                  />
                </Badge>
              ))}
          </div>
        )}
        <div className="flex gap-2">
          <Input
            value={customAllergyInput}
            onChange={(e) => setCustomAllergyInput(e.target.value)}
            placeholder="Add custom allergy..."
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addCustomAllergy();
              }
            }}
          />
          <Button
            type="button"
            variant="outline"
            onClick={addCustomAllergy}
            disabled={!customAllergyInput.trim()}
          >
            Add
          </Button>
        </div>
      </div>

      {/* Preferred Language */}
      <div className="glass-card rounded-2xl p-4 space-y-2">
        <h2 className="text-foreground font-medium text-sm">Preferred Language</h2>
        <select
          value={preferredLanguage}
          onChange={(e) => setPreferredLanguage(e.target.value)}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          {SPEECH_LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
            </option>
          ))}
        </select>
      </div>

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <Button variant="gradient" onClick={handleSave} className="flex-1" disabled={updateProfile.isPending}>
          {updateProfile.isPending ? "Saving..." : "Save & Continue"}
        </Button>
        <Button variant="ghost" onClick={onSkip}>
          Skip
        </Button>
      </div>
    </div>
  );
}
