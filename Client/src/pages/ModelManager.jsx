import React from 'react';
import {
    Plus,
    Box,
    Info,
    CodeXml,
    Bot
} from 'lucide-react';
import SharedSidebar from './Sidebar';

// --- Data for the Model Cards ---
// In a real app, this would likely come from an API.
const modelsData = [
    {
        id: 1,
        name: 'Qwen2.5-VL-3B',
        type: 'Vision / Document',
        size: '3B',
        description: 'Vision, image and document understanding',
        state: 'Loaded',
        icon: 'vision' // We use this key to pick the right icon component
    },
    {
        id: 2,
        name: 'Qwen2.5-Coder-3B',
        type: 'Code generation',
        size: '5B',
        description: 'Code generation, debugging and explanation',
        state: 'Loaded',
        icon: 'code'
    },
    {
        id: 3,
        name: 'Llama 3.2 3B',
        type: 'Language model',
        size: '3B',
        description: 'General reasoning and text generation',
        state: 'Available',
        icon: 'llama'
    }
];

// --- Components ---

// Dynamic Model Card Component
const ModelCard = ({ model }) => {
    // Helper to render the correct icon based on the data
    const renderIcon = () => {
        switch (model.icon) {
            case 'vision':
                return <Box size={24} className="text-gray-300" />;
            case 'code':
                return <CodeXml size={24} className="text-gray-300" />;
            case 'llama':
                return <Bot size={24} className="text-gray-300" />;
            default:
                return <Box size={24} className="text-gray-300" />;
        }
    };

    // Helper for the state badge styling
    const isLoaded = model.state === 'Loaded';

    return (
        <div className="bg-[#111111] border border-[#222222] rounded-xl overflow-hidden mb-4">
            {/* Table Headers (only shown conceptually, actual layout is CSS Grid) */}
            <div className="grid grid-cols-12 gap-4 p-4 items-center text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-[#222222]/50">
                <div className="col-span-4 pl-2">Model</div>
                <div className="col-span-2">Type</div>
                <div className="col-span-1 text-center">Size</div>
                <div className="col-span-3 flex items-center gap-1">
                    Specifications
                </div>
                <div className="col-span-2 text-center">State</div>
            </div>

            {/* Model Row */}
            <div className="grid grid-cols-12 gap-4 p-4 items-center">
                {/* Model Name & Icon */}
                <div className="col-span-4 flex items-center gap-3 pl-2">
                    <div className="w-8 h-8 rounded bg-[#1a1a1a] flex items-center justify-center border border-[#2a2a2a]">
                        {renderIcon()}
                    </div>
                    <span className="text-white font-semibold text-lg">{model.name}</span>
                </div>

                {/* Type */}
                <div className="col-span-2 text-gray-400 text-sm">
                    {model.type}
                </div>

                {/* Size */}
                <div className="col-span-1 text-center text-gray-400 text-sm">
                    {model.size}
                </div>

                {/* Specifications (Info Icon + Text) */}
                <div className="col-span-3 flex items-center gap-2 text-gray-400 text-sm">
                    <Info size={16} className="text-gray-500 shrink-0" />
                    <span className="leading-tight">{model.description}</span>
                </div>

                {/* State Badge */}
                <div className="col-span-2 flex justify-center">
                    <span
                        className={`px-4 py-1.5 rounded-full text-xs font-medium border ${isLoaded
                            ? 'bg-[#0f1f33] text-[#4a9eff] border-[#1e3a5f]'
                            : 'bg-transparent text-gray-400 border-[#333333]'
                            }`}
                    >
                        {model.state}
                    </span>
                </div>
            </div>
        </div>
    );
};


// 3. Main Content Area
const MainContent = () => {
    return (
        <main className="flex-1 bg-black flex flex-col h-screen overflow-y-auto">
            <div className="max-w-6xl w-full mx-auto px-10 py-10">

                {/* Page Header */}
                <header className="mb-10">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-2">
                                Local Inference
                            </p>
                            <h1 className="text-4xl font-semibold text-white mb-2">
                                Model Manager
                            </h1>
                            <p className="text-gray-400 text-sm">
                                Manage the models available to automatic backend routing.
                            </p>
                        </div>

                        <button className="flex items-center gap-2 bg-[#3b82f6] hover:bg-blue-600 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors">
                            <Plus size={18} />
                            Add Model
                        </button>
                    </div>
                </header>

                {/* Models List Container */}
                <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-2xl p-6">
                    {/* Map over the data array to generate cards dynamically */}
                    {modelsData.map((model) => (
                        <ModelCard key={model.id} model={model} />
                    ))}
                </div>

            </div>
        </main>
    );
};

// --- Main App ---

export default function ModelManager({ onNavigate }) {
    return (
        <div className="flex h-screen bg-black font-sans antialiased overflow-hidden selection:bg-blue-500/30">
            <SharedSidebar activePage="Model Manager" onNavigate={onNavigate} />
            <MainContent />
        </div>
    );
}