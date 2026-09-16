import React, { useRef, useState } from 'react';
import {
    Paperclip,
    ArrowUp,
    X,
} from 'lucide-react';
import logo from '../assets/logo.png'
import Sidebar from './Sidebar';

const MainContent = () => {
    const fileInputRef = useRef(null);
    const [selectedFile, setSelectedFile] = useState(null);

    const handleFileSelected = (event) => {
        setSelectedFile(event.target.files?.[0] ?? null);
        event.target.value = '';
    };

    return (
        <main className="flex-1 bg-black flex flex-col relative h-screen">

            {/* Center Content */}
            <div className="flex-1 flex flex-col items-center justify-center px-4 max-w-3xl mx-auto w-full">

                {/* Central Logo */}
                <div className="flex items-center gap-1 mb-12">
                    <img
                        src={logo}
                        alt="SEAL Logo"
                        className="w-15 h-15 object-contain"
                    />
                    <span className="text-white font-light tracking-[0.3em] text-3xl">SEAL</span>
                </div>

                {/* Input Container */}
                <div className="w-full relative group">
                    <div className="absolute inset-0 bg-gradient-to-r from-gray-800 to-gray-900 rounded-2xl blur-md opacity-20 group-hover:opacity-30 transition-opacity"></div>

                    <div className="relative bg-[#1a1a1a] border border-gray-800 rounded-3xl p-2 pl-4 flex flex-col gap-2 shadow-2xl">

                        {selectedFile && (
                            <div className="flex items-center gap-2 self-start max-w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-300">
                                <span className="truncate">{selectedFile.name}</span>
                                <button
                                    type="button"
                                    onClick={() => setSelectedFile(null)}
                                    className="shrink-0 rounded-full p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
                                    aria-label="Remove attached file"
                                >
                                    <X size={14} />
                                </button>
                            </div>
                        )}

                        {/* Input Field */}
                        <div className="flex items-center w-full min-h-[56px]">
                            <textarea
                                rows="1"
                                placeholder="Ask anything..."
                                className="w-full min-h-[56px] max-h-60 resize-none overflow-y-auto bg-transparent text-gray-200 placeholder-gray-500 outline-none text-base leading-6 break-words"
                                onInput={(event) => {
                                    event.currentTarget.style.height = 'auto';
                                    event.currentTarget.style.height = `${event.currentTarget.scrollHeight}px`;
                                }}
                            />
                        </div>

                        {/* Action Bar */}
                        <div className="flex items-center justify-between pb-1">
                            <div className="flex items-center gap-1">
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.txt"
                                    onChange={handleFileSelected}
                                    className="hidden"
                                />
                                <button
                                    type="button"
                                    onClick={() => fileInputRef.current?.click()}
                                    className="p-2 rounded-full hover:bg-gray-800 text-gray-400 hover:text-gray-200 transition-colors"
                                    aria-label="Attach a file"
                                >
                                    <Paperclip size={18} />
                                </button>
                            </div>

                            <div className="flex items-center gap-3">
                                {/* Vertical Divider */}
                                <div className="h-5 w-[1px] bg-gray-700"></div>

                                {/* Submit Button */}
                                <button className="w-9 h-9 rounded-full bg-blue-500 hover:bg-blue-600 flex items-center justify-center text-white transition-colors">
                                    <ArrowUp size={20} />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

            </div>
        </main>
    );
};

// --- Main App ---

export default function Home({ onNavigate }) {
    return (
        <div className="flex h-screen bg-black font-sans antialiased overflow-hidden selection:bg-blue-500/30">
            <Sidebar activePage="Chats" onNavigate={onNavigate} />
            <MainContent />
        </div>
    );
}