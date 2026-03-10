import { Header } from "@/components/header";
import PageSpeedAnalyzer from "./PageSpeedAnalyzer";

export default function PageSpeedPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="mx-auto max-w-5xl space-y-8 px-6 py-12">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Core Web Vitals & PageSpeed
          </h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Run a lab-based PageSpeed snapshot and validate performance signals
            that impact SEO and AI visibility.
          </p>
        </div>

        <PageSpeedAnalyzer />
      </main>
    </div>
  );
}
