import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Temporary Jest compatibility while test files are migrated.
(globalThis as unknown as { jest?: typeof vi }).jest = vi;

if (!process.env.NEXT_PUBLIC_API_URL) {
  process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";
}

if (!process.env.API_URL) {
  process.env.API_URL = "http://localhost:8000";
}

if (!HTMLElement.prototype.hasPointerCapture) {
  HTMLElement.prototype.hasPointerCapture = () => false;
}

if (!HTMLElement.prototype.setPointerCapture) {
  HTMLElement.prototype.setPointerCapture = () => {};
}

if (!HTMLElement.prototype.releasePointerCapture) {
  HTMLElement.prototype.releasePointerCapture = () => {};
}

if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = () => {};
}
