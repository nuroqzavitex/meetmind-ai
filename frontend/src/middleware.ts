import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server"
import { NextResponse } from "next/server"

const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"])
const isSelectOrg = createRouteMatcher(["/select-org(.*)"])
const isApiRoute = createRouteMatcher(["/(api|trpc)(.*)"])

export default clerkMiddleware(async (auth, req) => {
  if (isPublicRoute(req)) return
  await auth.protect()
  const { orgId } = await auth()
  if (!orgId && !isSelectOrg(req) && !isApiRoute(req)) {
    return NextResponse.redirect(new URL("/select-org", req.url))
  }
}, { signInUrl: "/sign-in", signUpUrl: "/sign-up" })

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
}
