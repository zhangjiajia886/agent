import { Construction } from 'lucide-react';

interface PlaceholderPageProps {
  title: string;
  description: string;
  phase: string;
}

export default function PlaceholderPage({ title, description, phase }: PlaceholderPageProps) {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center max-w-md">
        <Construction size={48} className="mx-auto mb-4 text-gray-300" />
        <h2 className="text-lg font-semibold text-gray-800 mb-1">{title}</h2>
        <p className="text-sm text-gray-500 mb-4">{description}</p>
        <span className="text-xs bg-purple-50 text-purple-600 px-3 py-1 rounded-full">
          {phase}
        </span>
      </div>
    </div>
  );
}
