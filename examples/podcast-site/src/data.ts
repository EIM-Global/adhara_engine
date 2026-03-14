// ============================================================================
// Podcast Site Data
// ============================================================================
// All content is defined here for easy customization.
// Edit this file to make the site your own.

export interface Episode {
  id: number;
  title: string;
  description: string;
  date: string;
  duration: string;
  number: number;
}

export interface SubscribeLink {
  name: string;
  href: string;
}

export const siteConfig = {
  podcastName: "The Build Log",
  tagline: "Stories from the command line",
  description:
    "A weekly podcast where we dig into the real stories behind building software. From deploy scripts to database migrations, from open source contributions to production incidents — these are the tales developers tell over coffee.",

  host: {
    name: "Alex Chen",
    bio: "Alex is a software engineer who has spent 15 years building and breaking things in production. After stints at startups and big tech, they now focus on open source tooling and self-hosted infrastructure. The Build Log is their way of sharing the lessons that only come from shipping real software.",
    role: "Host & Producer",
  },

  copyright: `${new Date().getFullYear()} The Build Log. All rights reserved.`,
};

export const episodes: Episode[] = [
  {
    id: 1,
    number: 42,
    title: "Why We Self-Host Everything",
    description:
      "We dive into the philosophy and practicalities of self-hosting. From DNS to databases, what does it really take to own your infrastructure? We discuss cost savings, control, and the surprising amount of sleep you lose.",
    date: "Mar 7, 2026",
    duration: "47 min",
  },
  {
    id: 2,
    number: 41,
    title: "The Art of the Deploy Script",
    description:
      "Every team has one — that magical shell script that somehow holds everything together. We explore what makes a great deployment pipeline and why the best ones are boring.",
    date: "Feb 28, 2026",
    duration: "38 min",
  },
  {
    id: 3,
    number: 40,
    title: "Docker in Production: Lessons Learned",
    description:
      "Three years of running containers in production, distilled into hard-won lessons. We talk about image sizes, health checks, logging, and the day we accidentally deleted the wrong volume.",
    date: "Feb 21, 2026",
    duration: "52 min",
  },
  {
    id: 4,
    number: 39,
    title: "Open Source Maintainer Burnout",
    description:
      "An honest conversation about the human side of open source. What happens when your side project becomes critical infrastructure for thousands of developers? We discuss boundaries, funding, and saying no.",
    date: "Feb 14, 2026",
    duration: "44 min",
  },
  {
    id: 5,
    number: 38,
    title: "Database Migrations at 3 AM",
    description:
      "The story of a schema migration that went sideways and the 72-hour recovery effort that followed. We break down what went wrong, what we learned, and the runbook we wrote after.",
    date: "Feb 7, 2026",
    duration: "41 min",
  },
];

export const subscribeLinks: SubscribeLink[] = [
  { name: "Apple Podcasts", href: "#" },
  { name: "Spotify", href: "#" },
  { name: "RSS Feed", href: "#" },
  { name: "YouTube", href: "#" },
];

export const socialLinks = [
  { name: "Twitter", href: "#" },
  { name: "GitHub", href: "#" },
  { name: "Mastodon", href: "#" },
];
