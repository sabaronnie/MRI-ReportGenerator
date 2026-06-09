"use client";

import { Button } from "@/components/ui/button";
import {
	InputGroup,
	InputGroupAddon,
	InputGroupInput,
} from "@/components/ui/input-group";
import { FloatingPaths } from "@/components/floating-paths";
import { AtSignIcon, LockIcon } from "lucide-react";
import { login } from "@/lib/auth/actions";
import { Brand } from "@/components/brand";

export function AuthPage({ error }: { error?: boolean }) {
	return (
		<div className="relative md:h-screen md:overflow-hidden lg:grid lg:grid-cols-2">
			<div className="relative hidden h-full flex-col border-r bg-secondary p-10 lg:flex">
				<div className="absolute inset-0 bg-linear-to-b from-transparent via-transparent to-background" />
				<Brand className="z-10 mr-auto" />

				<div className="z-10 mt-auto max-w-md">
					<blockquote className="space-y-2">
						<p className="font-serif text-2xl leading-snug">
							Structured cervical-spine MRI measurements and triage notes for
							every level — drafted in seconds, signed by you.
						</p>
						<footer className="font-mono text-sm text-muted-foreground">
							Cervical MRI Reporting — clinician-in-the-loop
						</footer>
					</blockquote>
				</div>
				<div className="absolute inset-0">
					<FloatingPaths position={1} />
					<FloatingPaths position={-1} />
				</div>
			</div>
			<div className="relative flex min-h-screen flex-col justify-center px-8">
				{/* Top Shades */}
				<div
					aria-hidden
					className="absolute inset-0 isolate -z-10 opacity-60 contain-strict"
				>
					<div className="absolute top-0 right-0 h-320 w-140 -translate-y-87.5 rounded-full bg-[radial-gradient(68.54%_68.72%_at_55.02%_31.46%,--theme(--color-foreground/.06)_0,hsla(0,0%,55%,.02)_50%,--theme(--color-foreground/.01)_80%)]" />
					<div className="absolute top-0 right-0 h-320 w-60 rounded-full bg-[radial-gradient(50%_50%_at_50%_50%,--theme(--color-foreground/.04)_0,--theme(--color-foreground/.01)_80%,transparent_100%)] [translate:5%_-50%]" />
					<div className="absolute top-0 right-0 h-320 w-60 -translate-y-87.5 rounded-full bg-[radial-gradient(50%_50%_at_50%_50%,--theme(--color-foreground/.04)_0,--theme(--color-foreground/.01)_80%,transparent_100%)]" />
				</div>

				<div className="mx-auto space-y-5 sm:w-sm">
					<Brand className="lg:hidden" />
					<div className="flex flex-col space-y-1">
						<h1 className="font-serif text-3xl font-semibold tracking-tight">
							Sign in
						</h1>
						<p className="text-base text-muted-foreground">
							Access your cervical-spine reporting workspace.
						</p>
						{error ? (
							<p className="text-sm text-rose-600">
								Could not sign you in. Try again.
							</p>
						) : null}
					</div>
					<form action={login} className="space-y-3">
						<div className="space-y-1.5">
							<label htmlFor="email" className="text-sm font-medium text-foreground">
								Email
							</label>
							<InputGroup>
								<InputGroupInput
									id="email"
									name="email"
									placeholder="you@hospital.org"
									type="email"
									autoComplete="email"
									required
								/>
								<InputGroupAddon align="inline-start">
									<AtSignIcon />
								</InputGroupAddon>
							</InputGroup>
						</div>
						<div className="space-y-1.5">
							<label htmlFor="password" className="text-sm font-medium text-foreground">
								Password
							</label>
							<InputGroup>
								<InputGroupInput
									id="password"
									name="password"
									placeholder="••••••••"
									type="password"
									autoComplete="current-password"
									required
								/>
								<InputGroupAddon align="inline-start">
									<LockIcon />
								</InputGroupAddon>
							</InputGroup>
						</div>

						<Button className="w-full" type="submit">
							Sign in
						</Button>
						<p className="text-center text-xs text-muted-foreground">
							Demo: <span className="font-mono">admin@demo</span> /{" "}
							<span className="font-mono">demo12345</span>
						</p>
					</form>
					<p className="mt-8 text-muted-foreground text-sm">
						By continuing, you agree to our{" "}
						<a
							className="underline underline-offset-4 hover:text-primary"
							href="#"
						>
							Terms of Service
						</a>{" "}
						and{" "}
						<a
							className="underline underline-offset-4 hover:text-primary"
							href="#"
						>
							Privacy Policy
						</a>
						.
					</p>
				</div>
			</div>
		</div>
	);
}
