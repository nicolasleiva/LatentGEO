import type { MockInstance, vi } from "vitest";

declare global {
  const jest: typeof vi;

  namespace jest {
    type Mock<
      T extends (...args: any[]) => any = (...args: any[]) => any,
    > = MockInstance<T>;
  }
}

export {};

