"use client";

import { useState } from "react";
import { AnalyzePageHeader } from "../../components/dashboard/analyze/AnalyzePageHeader";
import { AnalysisConfigCard } from "../../components/dashboard/analyze/AnalysisConfigCard";
import { ResultsCard } from "../../components/dashboard/analyze/ResultsCard";
import type { ClassifyResult, AnalyzeResult } from "@/lib/api";

type AnyResult = ClassifyResult | AnalyzeResult;

export default function AnalyzePage() {
  const [results, setResults] = useState<AnyResult[]>([]);

  return (
    <div className="space-y-6 max-w-5xl">
      <AnalyzePageHeader />

      <AnalysisConfigCard results={results} onResults={setResults} />

      <ResultsCard results={results} />
    </div>
  );
}
