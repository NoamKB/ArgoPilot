"use client"; // Next.js requires error boundaries to be Client Components. It calls no service.

import { Button } from "@/components/ui/button";

/** Any unexpected error: a plain message and a retry, never a stack trace (FR-2.18). */
export default function ErrorPage({ retry }: { error: unknown; retry: () => void }) {
  return (
    <div role="alert" className="mt-4">
      <h1 className="text-2xl font-bold tracking-tight">Something went wrong</h1>
      <p className="mt-2">The page couldn&apos;t be shown. Check that the services are running, then try again.</p>
      <Button className="mt-4" onClick={() => retry()}>
        Try again
      </Button>
    </div>
  );
}
