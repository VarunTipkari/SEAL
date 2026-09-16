import React, { useRef, useState } from 'react';
import { Search, Mail, FileText, Eye } from 'lucide-react';
import Sidebar from './Sidebar';

// --- Data for the Documents List ---
const documentsData = [
    {
        id: 1,
        name: 'Product security brief.pdf',
        size: '2.4 MB',
        added: 'Today, 10:42',
        status: 'Indexed',
    },
    {
        id: 2,
        name: 'Model governance policy.docx',
        size: '840 KB',
        added: 'Yesterday, 16:18',
        status: 'Indexed',
    },
    // Add more documents here and they will automatically render
];

const KnowledgeBase = ({ onNavigate }) => {
    const fileInputRef = useRef(null);
    const [documents, setDocuments] = useState(documentsData);

    const handleDocumentsSelected = (event) => {
        const selectedDocuments = Array.from(event.target.files ?? []).map((file, index) => ({
            id: `${file.name}-${file.lastModified}-${index}`,
            name: file.name,
            size: `${(file.size / (1024 * 1024)).toFixed(2)} MB`,
            added: 'Just now',
            status: 'Pending',
        }));

        setDocuments((currentDocuments) => [...selectedDocuments, ...currentDocuments]);
        event.target.value = '';
    };

    return (
        <div className="flex h-screen bg-black font-sans antialiased overflow-hidden selection:bg-blue-500/30">
            {/* Sidebar with activePage prop */}
            <Sidebar activePage="Knowledge Base" onNavigate={onNavigate} />

            {/* Main Content */}
            <main className="flex-1 bg-black flex flex-col h-screen overflow-y-auto">
                <div className="max-w-6xl w-full mx-auto px-10 py-10">
                    {/* Page Header */}
                    <header className="mb-10 flex justify-between items-start">
                        <div>
                            <p className="text-xs font-semibold text-[#3b82f6] uppercase tracking-widest mb-2">
                                Secure Storage
                            </p>
                            <h1 className="text-4xl font-semibold text-white mb-2">
                                Knowledge Base
                            </h1>
                            <p className="text-gray-400 text-sm">
                                Documents available to the private retrieval layer.
                            </p>
                        </div>

                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.txt"
                            multiple
                            onChange={handleDocumentsSelected}
                            className="hidden"
                        />
                        <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            className="flex items-center gap-2 bg-[#3b82f6] hover:bg-blue-600 text-white px-5 py-2.5 rounded-lg font-medium text-sm transition-colors"
                        >
                            <Mail size={18} />
                            Add Documents
                        </button>
                    </header>

                    {/* Search Bar */}
                    <div className="relative mb-6">
                        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                            <Search size={20} className="text-gray-500" />
                        </div>
                        <input
                            type="text"
                            placeholder="Search documents"
                            className="w-full bg-[#111111] border border-[#222222] text-white placeholder-gray-500 rounded-xl pl-12 pr-4 py-3.5 outline-none focus:border-[#3b82f6]/50 transition-colors text-sm"
                        />
                    </div>

                    {/* Documents Table Container */}
                    <div className="bg-[#111111] border border-[#222222] rounded-xl overflow-hidden">
                        {/* Table Header */}
                        <div className="grid grid-cols-[minmax(0,2fr)_minmax(80px,0.8fr)_minmax(110px,1fr)_auto_40px] gap-4 p-5 items-center text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-[#222222]">
                            <div className="min-w-0 pl-2">Document</div>
                            <div>Size</div>
                            <div>Added</div>
                            <div>Status</div>
                            <div></div>
                        </div>

                        {/* Dynamic Document Rows */}
                        <div className="flex flex-col">
                            {documents.map((doc) => (
                                <div
                                    key={doc.id}
                                    className="grid grid-cols-[minmax(0,2fr)_minmax(80px,0.8fr)_minmax(110px,1fr)_auto_40px] gap-4 p-4 items-center border-b border-[#222222]/50 last:border-b-0 hover:bg-[#1a1a1a] transition-colors"
                                >
                                    {/* Document Name & Icon */}
                                    <div className="min-w-0 flex items-center gap-3 pl-2">
                                        <div className="w-8 h-8 rounded bg-[#1a1a1a] flex items-center justify-center border border-[#2a2a2a]">
                                            <FileText size={16} className="text-gray-400" />
                                        </div>
                                        <span className="text-gray-200 text-sm font-medium truncate">
                                            {doc.name}
                                        </span>
                                    </div>

                                    {/* Size */}
                                    <div className="text-gray-400 text-sm">
                                        {doc.size}
                                    </div>

                                    {/* Added Date */}
                                    <div className="text-gray-400 text-sm">
                                        {doc.added}
                                    </div>

                                    {/* Status Badge */}
                                    <div className="flex items-center">
                                        <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-[#0f1f33] text-[#4a9eff] border border-[#1e3a5f]">
                                            <span className="w-1.5 h-1.5 rounded-full bg-[#4a9eff]"></span>
                                            {doc.status}
                                        </span>
                                    </div>

                                    {/* Action Button */}
                                    <div className="flex justify-end">
                                        <button type="button" aria-label={`View ${doc.name}`} className="p-1.5 rounded-full hover:bg-[#2a2a2a] text-gray-400 hover:text-white transition-colors">
                                            <Eye size={18} />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default KnowledgeBase;