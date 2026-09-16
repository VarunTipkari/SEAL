import React, { useState } from 'react';
import {
    Plus,
    Database,
    LayoutGrid,
    Search,
    MessageSquare,
    ChevronDown,
    ChevronRight,
    Settings,
    PanelLeftClose,
    PanelLeftOpen,
} from 'lucide-react';

// Optional: pass your logo as prop or import it here
import logo from '../assets/logo.png';

// --- Reusable Sidebar Item ---
const SidebarItem = ({ icon: Icon, label, active = false, collapsed = false, onClick }) => (
    <button
        type="button"
        onClick={onClick}
        className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm ${active
            ? 'bg-[#1a1a1a] text-white border-l-2 border-[#3b82f6]'
            : 'text-gray-400 hover:text-gray-200 hover:bg-[#1a1a1a]/50'
            } ${collapsed ? 'justify-center' : ''}`}
        title={collapsed ? label : ''} // tooltip when collapsed
    >
        <Icon size={18} className="shrink-0" />
        {!collapsed && <span className="truncate">{label}</span>}
    </button>
);

// --- Sidebar ---
const Sidebar = ({ activePage = 'Chats', onNavigate }) => {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [isChatsOpen, setIsChatsOpen] = useState(true);

    // Workspace nav items
    const workspaceItems = [
        { icon: Database, label: 'Knowledge Base' },
        { icon: LayoutGrid, label: 'Model Manager' },
    ];

    // Chat history items (only shown when not collapsed)
    const chatItems = [
        'Brain signal analysis',
        'Research summary',
        'UI design ideas',
        'Python script help',
        'EEG data processing',
    ];
    return (
        <aside
            className={`bg-black border-r border-[#1a1a1a] flex flex-col h-screen p-4 transition-all duration-300 ease-in-out shrink-0 ${isCollapsed ? 'w-20' : 'w-72'
                }`}
        >
            {/* Header */}
            <div
                className={`flex items-center mb-6 ${isCollapsed ? 'justify-center' : 'justify-between'
                    }`}
            >
                {!isCollapsed && (
                    <div className="flex items-center gap-2">
                        <img src={logo} alt="SEAL Logo" className="w-8 h-8 object-contain" />
                        <span className="text-white font-semibold tracking-wider text-lg">
                            SEAL
                        </span>
                    </div>
                )}
                <button
                    onClick={() => setIsCollapsed(!isCollapsed)}
                    className="text-gray-500 hover:text-white transition-colors p-1"
                    title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                >
                    {isCollapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={20} />}
                </button>
            </div>

            {/* New Chat Button */}
            <button
                type="button"
                onClick={() => onNavigate?.('Home')}
                className={`flex items-center justify-center gap-2 w-full bg-[#1a1a1a] hover:bg-gray-800 text-white py-2.5 rounded-xl mb-6 transition-all border border-[#2a2a2a] ${isCollapsed ? 'px-0' : ''
                    }`}
            >
                <Plus size={18} />
                {!isCollapsed && <span className="text-sm font-medium">New Chat</span>}
            </button>

            {/* Workspace Section */}
            <div className="mb-6">
                {!isCollapsed && (
                    <h3 className="text-xs font-semibold text-gray-600 mb-2 px-2 uppercase tracking-wider">
                        Workspace
                    </h3>
                )}
                <div className="space-y-1">
                    {workspaceItems.map((item) => (
                        <SidebarItem
                            key={item.label}
                            icon={item.icon}
                            label={item.label}
                            active={activePage === item.label}
                            collapsed={isCollapsed}
                            onClick={() => onNavigate?.(item.label)}
                        />
                    ))}
                </div>
            </div>

            {/* Chats Section */}
            <div className="flex-1 overflow-y-auto custom-scrollbar">
                {!isCollapsed && (
                    <>
                        <div className="flex items-center justify-between px-2 mb-2">
                            <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                Chats
                            </h3>
                            <div className="flex gap-2 text-gray-500">
                                <Search size={14} className="cursor-pointer hover:text-white" />
                                <Plus size={14} className="cursor-pointer hover:text-white" />
                            </div>
                        </div>

                        <div className="mb-4">
                            <div
                                className="flex items-center gap-1 text-gray-400 text-xs font-medium px-2 py-1 cursor-pointer hover:text-white"
                                onClick={() => setIsChatsOpen(!isChatsOpen)}
                            >
                                {isChatsOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                <span>Today</span>
                            </div>

                            {isChatsOpen && (
                                <div className="mt-1 space-y-0.5">
                                    {chatItems.map((label) => (
                                        <SidebarItem key={label} icon={MessageSquare} label={label} />
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="space-y-1">
                            {['Yesterday', 'Last 7 days', 'This month', 'Archived'].map((label) => (
                                <div
                                    key={label}
                                    className="flex items-center gap-1 text-gray-400 text-xs font-medium px-2 py-2 cursor-pointer hover:text-white"
                                >
                                    <ChevronRight size={14} />
                                    <span>{label}</span>
                                </div>
                            ))}
                        </div>
                    </>
                )}

                {/* Collapsed view - show only icons for recent chats */}
                {isCollapsed && (
                    <div className="space-y-1">
                        {chatItems.slice(0, 5).map((label) => (
                            <SidebarItem
                                key={label}
                                icon={MessageSquare}
                                label={label}
                                collapsed={true}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* User Profile Footer */}
            <div
                className={`mt-4 pt-4 border-t border-[#1a1a1a] flex items-center ${isCollapsed ? 'justify-center' : 'justify-between px-2'
                    }`}
            >
                <div className="flex items-center gap-3 cursor-pointer">
                    <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-white text-sm font-medium shrink-0">
                        U
                    </div>
                    {!isCollapsed && (
                        <span className="text-sm text-white font-medium">User</span>
                    )}
                </div>
                {!isCollapsed && (
                    <Settings size={18} className="text-gray-400 cursor-pointer hover:text-white" />
                )}
            </div>
        </aside >
    );
};

export default Sidebar;