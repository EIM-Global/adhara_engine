import {
  Mic,
  Play,
  Clock,
  Calendar,
  Headphones,
  Rss,
  Github,
  Twitter,
  Radio,
  ChevronRight,
  User,
} from "lucide-react";
import { siteConfig, episodes, subscribeLinks, socialLinks } from "./data";

function HeroSection() {
  return (
    <section className="relative overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-blue-600/20 via-slate-950 to-slate-950" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-500/10 via-transparent to-transparent" />

      <div className="relative mx-auto max-w-5xl px-6 pt-32 pb-24">
        <div className="flex flex-col items-center text-center">
          {/* Host avatar placeholder */}
          <div className="mb-8 flex h-28 w-28 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/25">
            <Mic className="h-12 w-12 text-white" />
          </div>

          <h1 className="mb-4 text-5xl font-bold tracking-tight text-white sm:text-6xl lg:text-7xl">
            {siteConfig.podcastName}
          </h1>
          <p className="mb-8 text-xl text-slate-400 sm:text-2xl">
            {siteConfig.tagline}
          </p>

          {/* Subscribe buttons */}
          <div className="flex flex-wrap justify-center gap-4">
            <a
              href="#subscribe"
              className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-6 py-3 font-medium text-white transition hover:bg-blue-500"
            >
              <Headphones className="h-5 w-5" />
              Subscribe Now
            </a>
            <a
              href="#episodes"
              className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-6 py-3 font-medium text-slate-300 transition hover:border-slate-500 hover:text-white"
            >
              <Play className="h-5 w-5" />
              Latest Episodes
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

function AboutSection() {
  return (
    <section id="about" className="mx-auto max-w-5xl px-6 py-24">
      <div className="grid gap-12 md:grid-cols-5">
        <div className="md:col-span-3">
          <h2 className="mb-2 text-sm font-semibold tracking-widest text-blue-400 uppercase">
            About the Show
          </h2>
          <h3 className="mb-6 text-3xl font-bold text-white">
            Real stories from real engineers
          </h3>
          <p className="text-lg leading-relaxed text-slate-400">
            {siteConfig.description}
          </p>
        </div>

        <div className="md:col-span-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-6">
            {/* Host avatar */}
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600">
              <User className="h-8 w-8 text-white" />
            </div>
            <p className="mb-1 text-sm text-slate-500">
              {siteConfig.host.role}
            </p>
            <h4 className="mb-3 text-xl font-semibold text-white">
              {siteConfig.host.name}
            </h4>
            <p className="text-sm leading-relaxed text-slate-400">
              {siteConfig.host.bio}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function EpisodeCard({
  episode,
}: {
  episode: (typeof episodes)[0];
}) {
  return (
    <article className="group rounded-2xl border border-slate-800 bg-slate-900/50 p-6 transition hover:border-slate-700 hover:bg-slate-900">
      <div className="mb-4 flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-600/10 text-sm font-bold text-blue-400">
          {episode.number}
        </span>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
          <span className="inline-flex items-center gap-1">
            <Calendar className="h-3.5 w-3.5" />
            {episode.date}
          </span>
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" />
            {episode.duration}
          </span>
        </div>
      </div>

      <h4 className="mb-2 text-lg font-semibold text-white group-hover:text-blue-400 transition">
        {episode.title}
      </h4>
      <p className="mb-4 text-sm leading-relaxed text-slate-400">
        {episode.description}
      </p>

      <button className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-400 transition hover:text-blue-300">
        <Play className="h-4 w-4" />
        Play Episode
        <ChevronRight className="h-3.5 w-3.5" />
      </button>
    </article>
  );
}

function EpisodesSection() {
  return (
    <section id="episodes" className="mx-auto max-w-5xl px-6 py-24">
      <div className="mb-12 text-center">
        <h2 className="mb-2 text-sm font-semibold tracking-widest text-blue-400 uppercase">
          Episodes
        </h2>
        <h3 className="text-3xl font-bold text-white">Latest from the log</h3>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {episodes.map((episode) => (
          <EpisodeCard key={episode.id} episode={episode} />
        ))}
      </div>
    </section>
  );
}

function SubscribeIcon({ name }: { name: string }) {
  switch (name) {
    case "Apple Podcasts":
      return <Headphones className="h-6 w-6" />;
    case "Spotify":
      return <Radio className="h-6 w-6" />;
    case "RSS Feed":
      return <Rss className="h-6 w-6" />;
    case "YouTube":
      return <Play className="h-6 w-6" />;
    default:
      return <Headphones className="h-6 w-6" />;
  }
}

function SubscribeSection() {
  return (
    <section id="subscribe" className="mx-auto max-w-5xl px-6 py-24">
      <div className="rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-900/50 p-8 text-center sm:p-12">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-blue-600/10">
          <Headphones className="h-8 w-8 text-blue-400" />
        </div>
        <h2 className="mb-2 text-sm font-semibold tracking-widest text-blue-400 uppercase">
          Subscribe
        </h2>
        <h3 className="mb-4 text-3xl font-bold text-white">
          Never miss an episode
        </h3>
        <p className="mx-auto mb-8 max-w-lg text-slate-400">
          Follow The Build Log on your favorite podcast platform. New episodes
          drop every Friday.
        </p>

        <div className="flex flex-wrap justify-center gap-4">
          {subscribeLinks.map((link) => (
            <a
              key={link.name}
              href={link.href}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/50 px-5 py-3 font-medium text-slate-300 transition hover:border-blue-500/50 hover:bg-slate-800 hover:text-white"
            >
              <SubscribeIcon name={link.name} />
              {link.name}
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}

function SocialIcon({ name }: { name: string }) {
  switch (name) {
    case "Twitter":
      return <Twitter className="h-5 w-5" />;
    case "GitHub":
      return <Github className="h-5 w-5" />;
    default:
      return <Radio className="h-5 w-5" />;
  }
}

function Footer() {
  return (
    <footer className="border-t border-slate-800">
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-6 px-6 py-12 sm:flex-row sm:justify-between">
        <div className="flex items-center gap-2 text-slate-500">
          <Mic className="h-5 w-5 text-blue-500" />
          <span className="text-sm">{siteConfig.copyright}</span>
        </div>

        <div className="flex items-center gap-4">
          {socialLinks.map((link) => (
            <a
              key={link.name}
              href={link.href}
              aria-label={link.name}
              className="text-slate-500 transition hover:text-white"
            >
              <SocialIcon name={link.name} />
            </a>
          ))}
        </div>
      </div>
    </footer>
  );
}

export default function App() {
  return (
    <div className="min-h-screen">
      <HeroSection />
      <AboutSection />
      <EpisodesSection />
      <SubscribeSection />
      <Footer />
    </div>
  );
}
