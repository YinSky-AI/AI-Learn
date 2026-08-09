"use client";

import { Button } from "@/components/ui/button";

export const MAX_SOLUTION_STEPS = 12;

interface SolutionStepsInputProps {
  value: string[];
  onChange: (steps: string[]) => void;
  disabled?: boolean;
}

export function SolutionStepsInput({ value, onChange, disabled = false }: SolutionStepsInputProps) {
  const rows = value.length ? value : [""];

  function updateStep(index: number, step: string) {
    const next = [...rows];
    next[index] = step;
    onChange(next.slice(0, MAX_SOLUTION_STEPS));
  }

  function removeStep(index: number) {
    const next = rows.filter((_, rowIndex) => rowIndex !== index);
    onChange(next.length ? next : [""]);
  }

  return (
    <fieldset className="mt-4 rounded-xl border border-blue-100 bg-blue-50/50 p-4" disabled={disabled}>
      <legend className="px-1 text-sm font-semibold text-gray-800">解题步骤（选填）</legend>
      <p className="mb-3 text-xs leading-5 text-gray-600">按顺序写出等式变形，空白行不会提交。</p>
      <ol className="space-y-2">
        {rows.map((step, index) => (
          <li key={index} className="flex items-center gap-2">
            <span className="w-6 shrink-0 text-center text-sm font-semibold text-blue-700">{index + 1}</span>
            <input
              value={step}
              onChange={(event) => updateStep(index, event.target.value)}
              maxLength={200}
              placeholder={index === 0 ? "例如：2x + 3 = 11" : "写出下一步等式"}
              aria-label={`第 ${index + 1} 步`}
              className="min-h-11 flex-1 rounded-lg border border-gray-300 bg-white px-3 text-sm outline-none focus:border-brand-blue focus:ring-2 focus:ring-blue-100"
            />
            <Button type="button" variant="ghost" size="sm" onClick={() => removeStep(index)} aria-label={`删除第 ${index + 1} 步`}>
              删除
            </Button>
          </li>
        ))}
      </ol>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mt-3"
        disabled={disabled || rows.length >= MAX_SOLUTION_STEPS}
        onClick={() => onChange([...rows, ""])}
      >
        添加一步
      </Button>
      <span className="ml-3 text-xs text-gray-500">{rows.length}/{MAX_SOLUTION_STEPS}</span>
    </fieldset>
  );
}
