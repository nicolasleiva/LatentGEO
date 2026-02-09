'use client';

import { useState, useEffect } from 'react';

interface AIProcessingScreenProps {
  isProcessing: boolean;
}

const processingMessages = [
  'Initializing AI analysis engine',
  'Scanning your website',
  'Analyzing page structure',
  'Detecting technical issues',
  'Crawling competitor data',
  'Processing content with LLM',
  'Identifying optimization gaps',
  'Generating recommendations',
  'Training models on your data',
  'Synthesizing insights',
  'Almost there',
];

export function AIProcessingScreen({ isProcessing }: AIProcessingScreenProps) {
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    if (!isProcessing) return;

    const interval = setInterval(() => {
      setIsVisible(false);
      
      setTimeout(() => {
        setCurrentMessageIndex((prev) => 
          prev >= processingMessages.length - 1 ? prev : prev + 1
        );
        setIsVisible(true);
      }, 300);
    }, 3500);

    return () => clearInterval(interval);
  }, [isProcessing]);

  if (!isProcessing) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black">
      {/* Ambient gradient background */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-purple-500/10 blur-[120px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-blue-500/10 blur-[100px] animate-pulse" />
      </div>

      {/* Main content */}
      <div className="relative z-10 flex flex-col items-center">
        {/* AI Orb Spinner */}
        <div className="relative mb-16">
          {/* Outer ring */}
          <div className="w-24 h-24 rounded-full border border-white/10 animate-[spin_8s_linear_infinite]" />
          
          {/* Middle ring */}
          <div className="absolute inset-2 w-20 h-20 rounded-full border border-purple-500/30 animate-[spin_5s_linear_infinite_reverse]" />
          
          {/* Inner ring */}
          <div className="absolute inset-4 w-16 h-16 rounded-full border border-blue-400/40 animate-[spin_3s_linear_infinite]" />
          
          {/* Core orb */}
          <div className="absolute inset-6 w-12 h-12 rounded-full bg-gradient-to-br from-purple-500 via-blue-500 to-cyan-400 animate-pulse shadow-[0_0_60px_rgba(147,51,234,0.5)]" />
          
          {/* Orbiting dot */}
          <div className="absolute inset-0 animate-[spin_4s_linear_infinite]">
            <div className="w-3 h-3 rounded-full bg-white shadow-[0_0_20px_rgba(255,255,255,0.8)] absolute -top-1.5 left-1/2 -translate-x-1/2" />
          </div>
        </div>

        {/* Status text */}
        <div className="h-8 flex items-center justify-center">
          <p 
            className={`text-lg font-light tracking-wide text-white/80 transition-all duration-300 ${
              isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
            }`}
          >
            {processingMessages[currentMessageIndex]}
            <span className="inline-flex ml-1">
              <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
              <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
              <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
            </span>
          </p>
        </div>

        {/* Subtle hint */}
        <p className="mt-8 text-sm text-white/30 font-light tracking-wider">
          This may take a few minutes
        </p>
      </div>
    </div>
  );
}
