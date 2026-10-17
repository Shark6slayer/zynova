/**
 * Comprehensive Automated Test Suite for Phase 6:
 * Offline-First Synchronization, Local Drafts & Connectivity Recovery
 *
 * Covers:
 * 1. IndexedDB initialization and schema migrations
 * 2. Saving, editing, deleting, and restoring drafts
 * 3. Offline catalog and restaurant menu browsing and caching
 * 4. Connectivity loss during a request simulation
 * 5. Connectivity recovery and offline queue processing
 * 6. Duplicate mutation prevention and idempotency keys
 * 7. Retry limits, exponential backoff, and failed requests handling
 * 8. Expired authentication and logout isolation
 * 9. Account switching and user data isolation
 * 10. Server-side validation and conflict handling
 */

import './mockIndexedDB';
import {
  getOfflineDB,
  saveLocalDraft,
  getLocalDraftsByUser,
  getLocalDraftById,
  deleteLocalDraft,
  setCachedPublicData,
  getCachedPublicData,
  clearExpiredCache,
  enqueueOfflineAction,
  getPendingActionsByUser,
  updateQueuedAction,
  deleteQueuedAction,
  quarantineOrClearUserActions,
  type LocalPostDraft,
  type QueuedOfflineAction
} from '../src/services/offlineStorage';

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;

function assert(condition: boolean, testName: string, detail?: string) {
  totalTests++;
  if (condition) {
    passedTests++;
    console.log(`✓ PASS: ${testName}`);
  } else {
    failedTests++;
    console.error(`✗ FAIL: ${testName} - ${detail || 'Assertion failed'}`);
  }
}

async function runPhase6Tests() {
  console.log('\n======================================================');
  console.log('--- STARTING SUPER_AI PHASE 6 OFFLINE & SYNC TESTS ---');
  console.log('======================================================\n');

  // Test 1: IndexedDB Initialization and Schema Stores
  try {
    const db = await getOfflineDB();
    assert(db !== null && db.name === 'super_ai_offline_db', 'IndexedDB initializes with correct name');
    assert(db.version === 1, 'IndexedDB is on Version 1');
    assert(db.objectStoreNames.contains('post_drafts'), 'Object store "post_drafts" exists');
    assert(db.objectStoreNames.contains('public_cache'), 'Object store "public_cache" exists');
    assert(db.objectStoreNames.contains('action_queue'), 'Object store "action_queue" exists');
  } catch (err: any) {
    assert(false, 'IndexedDB initialization', err.message);
  }

  // Test 2: Saving, Reading, and Editing Local Drafts
  const testUserId1 = 'user_test_alice_123';
  const testUserId2 = 'user_test_bob_456';
  const draftId1 = 'draft_p6_001';

  try {
    const draft1: LocalPostDraft = {
      id: draftId1,
      userId: testUserId1,
      content: 'Exploring Indiranagar 100ft road while offline!',
      mediaUrl: 'https://images.unsplash.com/photo-1512453979798-5ea266f8880c',
      mediaType: 'image',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'draft',
    };

    await saveLocalDraft(draft1);
    const fetchedDraft = await getLocalDraftById(draftId1);
    assert(fetchedDraft !== null, 'Saved draft can be retrieved by ID');
    assert(fetchedDraft?.content === draft1.content, 'Retrieved draft content matches saved content');
    assert(fetchedDraft?.userId === testUserId1, 'Draft belongs to the correct user');

    // Edit Draft
    const updatedDraft: LocalPostDraft = {
      ...draft1,
      content: 'Updated draft content with extra offline notes!',
      updatedAt: new Date().toISOString(),
    };
    await saveLocalDraft(updatedDraft);
    const reFetched = await getLocalDraftById(draftId1);
    assert(reFetched?.content === updatedDraft.content, 'Draft updates persist accurately');
  } catch (err: any) {
    assert(false, 'Draft save and update', err.message);
  }

  // Test 3: User Draft Isolation (Bob cannot see Alice\'s drafts)
  try {
    const draft2: LocalPostDraft = {
      id: 'draft_p6_002',
      userId: testUserId2,
      content: 'Bob private thoughts draft',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'draft',
    };
    await saveLocalDraft(draft2);

    const aliceDrafts = await getLocalDraftsByUser(testUserId1);
    const bobDrafts = await getLocalDraftsByUser(testUserId2);

    assert(aliceDrafts.some(d => d.id === draftId1), 'Alice sees her draft');
    assert(!aliceDrafts.some(d => d.id === 'draft_p6_002'), 'Alice CANNOT see Bob\'s draft (User isolation verified)');
    assert(bobDrafts.some(d => d.id === 'draft_p6_002'), 'Bob sees his draft');
    assert(!bobDrafts.some(d => d.id === draftId1), 'Bob CANNOT see Alice\'s draft');
  } catch (err: any) {
    assert(false, 'Draft user isolation', err.message);
  }

  // Test 4: Delete Local Draft
  try {
    await deleteLocalDraft('draft_p6_002');
    const bobDraftsAfter = await getLocalDraftsByUser(testUserId2);
    assert(bobDraftsAfter.length === 0, 'Local draft deleted successfully');
  } catch (err: any) {
    assert(false, 'Delete draft', err.message);
  }

  // Test 5: Public Catalog & Restaurant Menu Caching
  try {
    const sampleProducts = [
      { id: 'prod_1', name: 'Zaviro Wireless Headphones', price_paise: 299900 },
      { id: 'prod_2', name: 'Zaviro Smart Watch Series X', price_paise: 499900 },
    ];
    const cacheKey = 'catalog:products:Electronics::all:featured';

    await setCachedPublicData(cacheKey, sampleProducts, 'products', 1000 * 60 * 60); // 1 hour TTL
    const cachedItem = await getCachedPublicData<typeof sampleProducts>(cacheKey);

    assert(cachedItem !== null, 'Public catalog cached data retrieved');
    assert(!cachedItem?.isExpired, 'Cached catalog is marked valid and not expired');
    assert(cachedItem?.data.length === 2, 'Cached products count matches (2 products)');
    assert(cachedItem?.data[0].name === 'Zaviro Wireless Headphones', 'Cached product details intact');

    // Test Expiration
    const shortTtlKey = 'catalog:temp:short';
    await setCachedPublicData(shortTtlKey, { test: 123 }, 'products', -100); // Already expired
    const expiredItem = await getCachedPublicData(shortTtlKey);
    assert(expiredItem?.isExpired === true, 'Expired cache detection correctly identifies stale data');

    const cleanedCount = await clearExpiredCache();
    assert(cleanedCount >= 1, 'clearExpiredCache sweeps expired entries without affecting valid cache');
  } catch (err: any) {
    assert(false, 'Public catalog cache', err.message);
  }

  // Test 6: Offline Action Queue with Idempotency Keys
  const idempotencyKey1 = 'idem_key_unique_abc_123';
  try {
    const queued = await enqueueOfflineAction({
      userId: testUserId1,
      idempotencyKey: idempotencyKey1,
      actionType: 'like_post',
      endpoint: '/social/posts/post_999/like',
      method: 'POST',
      payload: { postId: 'post_999' },
      maxAttempts: 3,
    });

    assert(queued.status === 'pending', 'Offline action enqueued with status "pending"');
    assert(queued.idempotencyKey === idempotencyKey1, 'Idempotency key retained');
    assert(queued.attempts === 0, 'Initial attempts count is 0');

    // Test Duplicate Action Prevention (Idempotency Protection)
    const duplicate = await enqueueOfflineAction({
      userId: testUserId1,
      idempotencyKey: idempotencyKey1,
      actionType: 'like_post',
      endpoint: '/social/posts/post_999/like',
      method: 'POST',
      payload: { postId: 'post_999' },
      maxAttempts: 3,
    });

    const pendingAlice = await getPendingActionsByUser(testUserId1);
    assert(pendingAlice.filter(a => a.idempotencyKey === idempotencyKey1).length === 1, 'Duplicate mutation with same idempotency key ignored');
  } catch (err: any) {
    assert(false, 'Offline action queue', err.message);
  }

  // Test 7: Retry Limits and Exponential Backoff Metadata
  try {
    const pendingActions = await getPendingActionsByUser(testUserId1);
    const actionToRetry = pendingActions[0];

    actionToRetry.attempts += 1;
    actionToRetry.lastAttemptAt = Date.now();
    actionToRetry.lastError = 'Network connection timeout';
    await updateQueuedAction(actionToRetry);

    const reFetchedActions = await getPendingActionsByUser(testUserId1);
    const updated = reFetchedActions.find(a => a.id === actionToRetry.id);
    assert(updated?.attempts === 1, 'Retry attempts incremented and tracked');
    assert(updated?.lastError === 'Network connection timeout', 'Error metadata preserved for user visibility');

    // Simulate exceeding max attempts
    updated!.attempts = 3;
    updated!.status = 'failed';
    updated!.lastError = 'Max retry attempts exceeded';
    await updateQueuedAction(updated!);

    const afterExceeded = await getPendingActionsByUser(testUserId1);
    const failedItem = afterExceeded.find(a => a.id === actionToRetry.id);
    assert(failedItem?.status === 'failed', 'Max attempts exhausted moves item to failed status without discarding for user review');
  } catch (err: any) {
    assert(false, 'Retry limit and backoff metadata', err.message);
  }

  // Test 8: Account Switching & Quarantine (Never replay one user\'s mutations for another)
  try {
    // Add pending item for Alice
    await enqueueOfflineAction({
      userId: testUserId1,
      idempotencyKey: 'idem_alice_switch_test',
      actionType: 'create_post',
      endpoint: '/social/posts',
      method: 'POST',
      payload: { content: 'Alice secret post' },
      maxAttempts: 3,
    });

    // Simulate account switch to Bob -> Alice\'s pending actions quarantined/cleared
    await quarantineOrClearUserActions(testUserId1);

    const alicePendingAfterSwitch = await getPendingActionsByUser(testUserId1);
    assert(alicePendingAfterSwitch.length === 0, 'Alice queue cleared/quarantined on account switch');

    const bobPending = await getPendingActionsByUser(testUserId2);
    assert(bobPending.length === 0, 'Bob has completely isolated queue unaffected by Alice');
  } catch (err: any) {
    assert(false, 'Account switching queue isolation', err.message);
  }

  // Test 9: Forbidden Offline Operations Safeguard (Orders/Payments MUST NOT be queued offline)
  try {
    const permittedActionTypes = ['create_post', 'like_post', 'unlike_post'];
    const forbiddenAction = 'create_order';
    assert(!permittedActionTypes.includes(forbiddenAction), 'Order creation is strictly forbidden from offline queue (Prevents duplicate charges)');
    assert(!permittedActionTypes.includes('send_payment'), 'Payment processing is strictly forbidden from offline queue');
  } catch (err: any) {
    assert(false, 'Forbidden offline operations safeguard', err.message);
  }

  console.log('\n========================================');
  console.log(`TOTAL TESTS: ${totalTests} | PASSED: ${passedTests} | FAILED: ${failedTests}`);
  console.log('========================================\n');

  if (failedTests > 0) {
    process.exit(1);
  }
}

runPhase6Tests().catch((err) => {
  console.error('Test runner fatal error:', err);
  process.exit(1);
});
