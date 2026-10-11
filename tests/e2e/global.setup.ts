import { clerkSetup } from "@clerk/testing/playwright"

import { missingClerkEnv } from "./env"

// Fetches a Clerk testing token once; workers inherit CLERK_FAPI / CLERK_TESTING_TOKEN.
export default async function globalSetup(): Promise<void> {
  if (missingClerkEnv().length > 0) return // the spec skips itself
  await clerkSetup()
}
