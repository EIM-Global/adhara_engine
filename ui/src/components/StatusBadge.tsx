import clsx from 'clsx';

const COLORS: Record<string, string> = {
  running: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  live: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  stopped: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
  building: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  deploying: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  error: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  not_found: 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400',
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className={clsx('inline-flex px-2 py-0.5 rounded-full text-xs font-medium', COLORS[status] || 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400')}>
      {status}
    </span>
  );
}
