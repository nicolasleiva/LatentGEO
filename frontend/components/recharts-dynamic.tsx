"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";

const loadRechartsComponent = (name: string) =>
  dynamic(
    () =>
      import("recharts").then(
        (mod) =>
          (mod as unknown as Record<string, ComponentType<any>>)[name],
      ),
    { ssr: false },
  ) as ComponentType<any>;

export const Area = loadRechartsComponent("Area");
export const AreaChart = loadRechartsComponent("AreaChart");
export const Bar = loadRechartsComponent("Bar");
export const BarChart = loadRechartsComponent("BarChart");
export const CartesianGrid = loadRechartsComponent("CartesianGrid");
export const Legend = loadRechartsComponent("Legend");
export const Line = loadRechartsComponent("Line");
export const LineChart = loadRechartsComponent("LineChart");
export const ResponsiveContainer = loadRechartsComponent("ResponsiveContainer");
export const Tooltip = loadRechartsComponent("Tooltip");
export const XAxis = loadRechartsComponent("XAxis");
export const YAxis = loadRechartsComponent("YAxis");
