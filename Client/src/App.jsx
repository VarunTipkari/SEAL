import { useState } from 'react';
import Home from './pages/Home';
import KnowledgeBase from './pages/KnowledgeBase.jsx';
import ModelManager from './pages/ModelManager.jsx';

export default function App() {
  const [currentPage, setCurrentPage] = useState('Home');

  const handleNavigate = (destination) => {
    const pageByNavigation = {
      Home: 'Home',
      'Knowledge Base': 'KnowledgeBase',
      'Model Manager': 'ModelManager',
    };

    setCurrentPage(pageByNavigation[destination] ?? 'Home');
  };

  switch (currentPage) {
    case 'KnowledgeBase':
      return <KnowledgeBase onNavigate={handleNavigate} />;
    case 'ModelManager':
      return <ModelManager onNavigate={handleNavigate} />;
    default:
      return <Home onNavigate={handleNavigate} />;
  }
}
