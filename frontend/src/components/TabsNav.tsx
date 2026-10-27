"use client";

import React from "react";
import { Clock, Globe, Shield, Award } from "lucide-react";

export type TabId = "timeline" | "geography" | "integrity" | "verdict";

interface TabsNavProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

const TABS: { id: TabId; label: string; icon: React.FC<{ className?: string }> }[] = [
  { id: "timeline", label: "Anatomia do Fluxo Temporal", icon: Clock },
  { id: "geography", label: "Geografia da Anomalia", icon: Globe },
  { id: "integrity", label: "Integridade & Biometria", icon: Shield },
  { id: "verdict", label: "Veredito Científico & Seções", icon: Award },
];

export const TabsNav: React.FC<TabsNavProps> = ({ activeTab, onTabChange }) => {
  return (
    <nav
      aria-label="Abas da Narrativa Científica"
      className="flex flex-wrap gap-1.5 border-b border-[#282D37] mb-6 pt-1"
    >
      {TABS.map((tab) => {
        const isActive = activeTab === tab.id;
        const Icon = tab.icon;
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            role="tab"
            aria-selected={isActive}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-xs sm:text-sm font-semibold transition-all border-t border-x ${
              isActive
                ? "bg-[#242933] text-[#38BDF8] border-[#282D37] border-b-2 border-b-[#38BDF8]"
                : "bg-[#181B20] text-[#94A3B8] border-[#282D37]/70 hover:text-[#E2E8F0] hover:bg-[#1f232b] border-b-transparent"
            }`}
          >
            <Icon className={`w-4 h-4 ${isActive ? "text-[#38BDF8]" : "text-[#64748B]"}`} />
            <span>{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
};
