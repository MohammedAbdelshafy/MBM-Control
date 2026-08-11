import React from 'react';
import MobileDialer from '@/pages/MobileDialer';

export default function MobileFirstGuard({ children }) {
  const isPhone = typeof window !== 'undefined'
    && window.matchMedia('(max-width: 767px)').matches;

  return isPhone ? <MobileDialer /> : children;
}
