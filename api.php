<?php
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Content-Type');
header('Access-Control-Allow-Methods: POST, OPTIONS');

date_default_timezone_set('America/Sao_Paulo');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit;
}

$configPath = __DIR__ . '/config.php';
$config = file_exists($configPath) ? require $configPath : array();
$storageDir = __DIR__ . '/data';
$storageFile = $storageDir . '/store.json';
$contentFile = $storageDir . '/content.json';

$input = json_decode(file_get_contents('php://input'), true);
if (!is_array($input)) {
    $input = $_POST;
}

$action = isset($input['action']) ? (string)$input['action'] : '';

try {
    switch ($action) {
        case 'create_group':
            createGroup($input, $config, $storageDir, $storageFile);
            break;
        case 'verify_admin':
            verifyAdmin($input, $config, $storageDir, $storageFile);
            break;
        case 'access_group':
            accessGroup($input, $storageDir, $storageFile);
            break;
        case 'toggle_progress':
            toggleProgress($input, $storageDir, $storageFile);
            break;
        case 'save_note':
            saveNote($input, $storageDir, $storageFile);
            break;
        case 'save_settings':
            saveSettings($input, $storageDir, $storageFile);
            break;
        case 'save_couple_journey':
            saveCoupleJourney($input, $storageDir, $storageFile);
            break;
        case 'get_content':
            getContent($storageDir, $contentFile);
            break;
        case 'save_day_content':
            saveDayContent($input, $config, $storageDir, $contentFile);
            break;
        case 'admin_stats':
            adminStats($input, $config, $storageDir, $storageFile);
            break;
        case 'admin_import_store':
            adminImportStore($input, $config, $storageDir, $storageFile);
            break;
        case 'admin_get_group':
            adminGetGroup($input, $config, $storageDir, $storageFile);
            break;
        case 'admin_unlock_days':
            adminUnlockDays($input, $config, $storageDir, $storageFile);
            break;
        case 'save_guidance':
            saveGuidance($input, $config, $storageDir, $storageFile);
            break;
        case 'save_private_note':
            savePrivateNote($input, $storageDir, $storageFile);
            break;
        case 'send_private_message':
            sendPrivateMessage($input, $storageDir, $storageFile);
            break;
        case 'delete_private_message':
            deletePrivateMessage($input, $storageDir, $storageFile);
            break;
        case 'admin_delete_private_message':
            adminDeletePrivateMessage($input, $config, $storageDir, $storageFile);
            break;
        case 'mark_private_chat_read':
            markPrivateChatRead($input, $config, $storageDir, $storageFile);
            break;
        case 'save_private_reply':
            savePrivateReply($input, $config, $storageDir, $storageFile);
            break;
        case 'admin_reset_private_password':
            adminResetPrivatePassword($input, $config, $storageDir, $storageFile);
            break;
        case 'private_note_status':
            privateNoteStatus($input, $storageDir, $storageFile);
            break;
        case 'unlock_private_note':
            unlockPrivateNote($input, $storageDir, $storageFile);
            break;
        case 'get_private_note':
            getPrivateNote($input, $storageDir, $storageFile);
            break;
        default:
            respond(false, 'Acao invalida.', null, 400);
    }
} catch (Throwable $error) {
    respond(false, 'Erro no servidor.', array('detail' => $error->getMessage()), 500);
}

function verifyAdmin($input, $config, $storageDir, $storageFile)
{
    assertAdmin($input, $config, $storageDir);
    activatePendingGroups($storageDir, $storageFile);

    respond(true, 'Acesso administrativo liberado.', array('verified' => true));
}

function createGroup($input, $config, $storageDir, $storageFile)
{
    assertAdmin($input, $config, $storageDir);

    $groupName = cleanText(isset($input['group_name']) ? $input['group_name'] : '');
    $partnerOne = cleanText(isset($input['partner_one']) ? $input['partner_one'] : '');
    $partnerTwo = cleanText(isset($input['partner_two']) ? $input['partner_two'] : '');
    $facilitator = cleanText(isset($input['facilitator_name']) ? $input['facilitator_name'] : '');
    $startDate = cleanDate(isset($input['start_date']) ? $input['start_date'] : date('Y-m-d'));
    $dailyUnlock = !empty($input['daily_unlock_enabled']);
    $requestedCode = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');

    if ($groupName === '' || $partnerOne === '' || $partnerTwo === '') {
        respond(false, 'Preencha o nome do casal e os dois participantes.', null, 422);
    }

    $created = null;

    updateStore($storageDir, $storageFile, function (&$store) use ($groupName, $partnerOne, $partnerTwo, $facilitator, $startDate, $dailyUnlock, $requestedCode, &$created) {
        $code = $requestedCode !== '' ? $requestedCode : generateCode($store);
        if (isset($store['groups'][$code])) {
            respond(false, 'Este codigo ja existe. Use outro codigo ou acesse o cadastro existente.', null, 409);
        }

        $now = date('c');

        $created = array(
            'code' => $code,
            'name' => $groupName,
            'type' => 'casal',
            'therapist' => $facilitator,
            'partnerOne' => $partnerOne,
            'partnerTwo' => $partnerTwo,
            'memberOneId' => 1,
            'memberTwoId' => 2,
            'completed' => array(),
            'notes' => new stdClass(),
            'guidance' => defaultGuidance(),
            'journeyShared' => defaultJourneyShared(),
            'notifications' => array(),
            'lastDay' => 1,
            'settings' => array(
                'startDate' => $startDate,
                'lockFutureDays' => $dailyUnlock,
                'manualUnlockedUntil' => 1,
            ),
            'createdAt' => $now,
            'activatedAt' => $now,
            'updatedAt' => $now,
        );

        $store['groups'][$code] = $created;
    });

    respond(true, 'Codigo criado com sucesso.', payload($created));
}

function accessGroup($input, $storageDir, $storageFile)
{
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $store = readStore($storageDir, $storageFile);

    if ($code === '' || !isset($store['groups'][$code])) {
        respond(false, 'Codigo nao encontrado.', null, 404);
    }

    $group = $store['groups'][$code];

    if (empty($group['activatedAt'])) {
        updateStore($storageDir, $storageFile, function (&$store) use ($code, &$group) {
            $store['groups'][$code]['activatedAt'] = date('c');
            $store['groups'][$code]['updatedAt'] = date('c');
            $group = $store['groups'][$code];
        });
    }

    respond(true, 'Acesso liberado.', payload($group));
}

function toggleProgress($input, $storageDir, $storageFile)
{
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $day = cleanDay(isset($input['day_number']) ? $input['day_number'] : 0);
    $completed = !empty($input['completed']);
    $group = null;

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $day, $completed, &$group) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }

        $days = isset($store['groups'][$code]['completed']) && is_array($store['groups'][$code]['completed'])
            ? $store['groups'][$code]['completed']
            : array();

        $days = array_values(array_filter($days, function ($item) use ($day) {
            return (int)$item !== $day;
        }));

        if ($completed) {
            $days[] = $day;
        }

        $days = array_values(array_unique(array_map('intval', $days)));
        sort($days);

        $store['groups'][$code]['completed'] = $days;
        $store['groups'][$code]['lastDay'] = count($days) ? min(max($days) + 1, 21) : 1;

        if (!isset($store['groups'][$code]['completedDates']) || !is_array($store['groups'][$code]['completedDates'])) {
            $store['groups'][$code]['completedDates'] = array();
        }
        if ($completed) {
            $store['groups'][$code]['completedDates'][$day] = date('Y-m-d');
        } else {
            unset($store['groups'][$code]['completedDates'][$day]);
        }
        $store['groups'][$code]['updatedAt'] = date('c');
        $group = $store['groups'][$code];
    });

    respond(true, 'Progresso salvo.', payload($group));
}

function saveNote($input, $storageDir, $storageFile)
{
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $memberId = isset($input['member_id']) ? (int)$input['member_id'] : 0;
    $day = cleanDay(isset($input['day_number']) ? $input['day_number'] : 0);
    $note = isset($input['note']) ? (string)$input['note'] : '';

    if ($memberId !== 1 && $memberId !== 2) {
        respond(false, 'Participante invalido.', null, 422);
    }

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $memberId, $day, $note) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }

        if (!isset($store['groups'][$code]['notes']) || !is_array($store['groups'][$code]['notes'])) {
            $store['groups'][$code]['notes'] = array();
        }
        if (!isset($store['groups'][$code]['notes'][$day]) || !is_array($store['groups'][$code]['notes'][$day])) {
            $store['groups'][$code]['notes'][$day] = array();
        }

        $store['groups'][$code]['notes'][$day][$memberId] = $note;
        $store['groups'][$code]['updatedAt'] = date('c');
    });

    respond(true, 'Anotacao salva.', null);
}

function saveSettings($input, $storageDir, $storageFile)
{
    respond(false, 'Somente a terapeuta pode alterar a liberacao dos dias pelo painel administrativo.', null, 403);

    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $startDate = cleanDate(isset($input['start_date']) ? $input['start_date'] : date('Y-m-d'));
    $dailyUnlock = !empty($input['daily_unlock_enabled']);
    $group = null;

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $startDate, $dailyUnlock, &$group) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }

        $previousSettings = isset($store['groups'][$code]['settings']) && is_array($store['groups'][$code]['settings'])
            ? $store['groups'][$code]['settings']
            : array();
        $manualUnlockedUntil = isset($previousSettings['manualUnlockedUntil'])
            ? cleanUnlockedDay($previousSettings['manualUnlockedUntil'])
            : 1;

        $store['groups'][$code]['settings'] = array_merge($previousSettings, array(
            'startDate' => $startDate,
            'lockFutureDays' => $dailyUnlock,
            'manualUnlockedUntil' => $manualUnlockedUntil,
        ));
        $store['groups'][$code]['updatedAt'] = date('c');
        $group = $store['groups'][$code];
    });

    respond(true, 'Configuracao salva.', payload($group));
}

function saveCoupleJourney($input, $storageDir, $storageFile)
{
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $journey = isset($input['journey_shared']) && is_array($input['journey_shared']) ? $input['journey_shared'] : array();
    $group = null;

    $clean = cleanJourneyShared($journey);

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $clean, &$group) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }

        $previous = isset($store['groups'][$code]['journeyShared']) && is_array($store['groups'][$code]['journeyShared'])
            ? array_merge(defaultJourneyShared(), $store['groups'][$code]['journeyShared'])
            : defaultJourneyShared();
        $changed = changedLabels($previous, $clean, journeyLabels());

        $store['groups'][$code]['journeyShared'] = $clean;
        if (count($changed)) {
            appendNotification($store['groups'][$code], array(
                'actor' => 'casal',
                'target' => 'caminhada',
                'title' => 'Nossa Caminhada atualizada',
                'summary' => 'Campos atualizados: ' . implode(', ', $changed) . '.',
            ));
        }
        $store['groups'][$code]['updatedAt'] = date('c');
        $group = $store['groups'][$code];
    });

    respond(true, 'Caminhada do casal salva.', payload($group));
}

function payload($group, $includePrivate = false)
{
    if (!isset($group['settings']) || !is_array($group['settings'])) {
        $group['settings'] = array();
    }
    $group['settings'] = array_merge(array(
        'startDate' => date('Y-m-d'),
        'lockFutureDays' => true,
        'manualUnlockedUntil' => 1,
    ), $group['settings']);
    $group['settings']['manualUnlockedUntil'] = cleanUnlockedDay($group['settings']['manualUnlockedUntil']);

    if (!isset($group['guidance']) || !is_array($group['guidance'])) {
        $group['guidance'] = defaultGuidance();
    }
    if (!isset($group['journeyShared']) || !is_array($group['journeyShared'])) {
        $group['journeyShared'] = defaultJourneyShared();
    }
    if (!isset($group['notifications']) || !is_array($group['notifications'])) {
        $group['notifications'] = array();
    }

    if (!$includePrivate) {
        unset($group['privateNotes']);
        unset($group['privateNotePasswords']);
        unset($group['privateReplies']);
        unset($group['privateChats']);
        unset($group['privateReadAt']);
    } else {
        for ($memberId = 1; $memberId <= 2; $memberId++) {
            ensurePrivateChat($group, $memberId);
            $group['privateChats'][$memberId] = privateChatForMember($group, $memberId);
        }
        $group['privateUnread'] = privateUnreadState($group);
    }

    return array(
        'group' => $group,
        'serverDate' => date('Y-m-d'),
        'serverNow' => date('c'),
        'journey' => array(
            'id' => 1,
            'title' => '21 Dias de Devocional para Casal',
            'slug' => '21-dias-casal',
            'audience' => 'casais',
            'description' => 'Um proposito de restauracao, unidade e presenca de Deus no relacionamento.',
            'totalDays' => 21,
        ),
    );
}

function getContent($storageDir, $contentFile)
{
    respond(true, 'Conteudo carregado.', array('content' => readContent($storageDir, $contentFile)));
}

function saveDayContent($input, $config, $storageDir, $contentFile)
{
    assertAdmin($input, $config, $storageDir);

    $day = cleanDay(isset($input['day_number']) ? $input['day_number'] : 0);
    $content = isset($input['content']) && is_array($input['content']) ? $input['content'] : array();

    $clean = array(
        'title' => cleanText(isset($content['title']) ? $content['title'] : ''),
        'intro' => cleanText(isset($content['intro']) ? $content['intro'] : ''),
        'reference' => cleanText(isset($content['reference']) ? $content['reference'] : ''),
        'scripture' => cleanText(isset($content['scripture']) ? $content['scripture'] : ''),
        'devotional' => cleanParagraphs(isset($content['devotional']) ? $content['devotional'] : array()),
        'renunciaShort' => cleanText(isset($content['renunciaShort']) ? $content['renunciaShort'] : ''),
        'renuncia' => cleanParagraphs(isset($content['renuncia']) ? $content['renuncia'] : array()),
        'acaoShort' => cleanText(isset($content['acaoShort']) ? $content['acaoShort'] : ''),
        'action' => cleanParagraphs(isset($content['action']) ? $content['action'] : array()),
        'prayer' => cleanParagraphs(isset($content['prayer']) ? $content['prayer'] : array()),
        'updatedAt' => date('c'),
    );

    if ($clean['title'] === '' || $clean['reference'] === '') {
        respond(false, 'Tema e referencia biblica sao obrigatorios.', null, 422);
    }

    updateContent($storageDir, $contentFile, function (&$contentStore) use ($day, $clean) {
        $contentStore[(string)$day] = $clean;
    });

    respond(true, 'Devocional atualizado sem alterar o progresso dos casais.', array('content' => readContent($storageDir, $contentFile)));
}

function adminStats($input, $config, $storageDir, $storageFile)
{
    assertAdmin($input, $config, $storageDir);

    $store = readStore($storageDir, $storageFile);
    $groups = isset($store['groups']) && is_array($store['groups']) ? $store['groups'] : array();
    $total = count($groups);
    $activated = 0;
    $recent = array();

    foreach ($groups as $group) {
        if (!empty($group['activatedAt'])) {
            $activated++;
        }

        $recent[] = array(
            'code' => isset($group['code']) ? $group['code'] : '',
            'name' => isset($group['name']) ? $group['name'] : '',
            'partnerOne' => isset($group['partnerOne']) ? $group['partnerOne'] : '',
            'partnerTwo' => isset($group['partnerTwo']) ? $group['partnerTwo'] : '',
            'createdAt' => isset($group['createdAt']) ? $group['createdAt'] : '',
            'activatedAt' => isset($group['activatedAt']) ? $group['activatedAt'] : '',
        );
    }

    usort($recent, function ($a, $b) {
        return strcmp($b['createdAt'], $a['createdAt']);
    });

    respond(true, 'Estatisticas carregadas.', array(
        'totalCodes' => $total,
        'activatedCodes' => $activated,
        'waitingCodes' => max(0, $total - $activated),
        'recent' => $recent,
    ));
}

function adminImportStore($input, $config, $storageDir, $storageFile)
{
    assertAdmin($input, $config, $storageDir);

    $incoming = null;
    if (isset($input['store']) && is_array($input['store'])) {
        $incoming = $input['store'];
    } elseif (isset($input['store_json'])) {
        $decoded = json_decode((string)$input['store_json'], true);
        if (is_array($decoded)) {
            $incoming = $decoded;
        }
    }

    if (!is_array($incoming) || !isset($incoming['groups']) || !is_array($incoming['groups'])) {
        respond(false, 'Arquivo de dados invalido para importacao.', null, 422);
    }

    $imported = 0;
    updateStore($storageDir, $storageFile, function (&$store) use ($incoming, &$imported) {
        if (!isset($store['groups']) || !is_array($store['groups'])) {
            $store['groups'] = array();
        }

        foreach ($incoming['groups'] as $code => $group) {
            if (!is_array($group)) {
                continue;
            }

            $normalizedCode = normalizeCode(isset($group['code']) ? $group['code'] : $code);
            if ($normalizedCode === '') {
                continue;
            }

            $group['code'] = $normalizedCode;
            if (empty($group['activatedAt'])) {
                $group['activatedAt'] = !empty($group['createdAt']) ? $group['createdAt'] : date('c');
            }
            $group['updatedAt'] = date('c');

            $store['groups'][$normalizedCode] = $group;
            $imported++;
        }
    });

    respond(true, 'Dados importados com sucesso.', array('imported' => $imported));
}

function adminGetGroup($input, $config, $storageDir, $storageFile)
{
    assertAdmin($input, $config, $storageDir);

    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $store = readStore($storageDir, $storageFile);

    if ($code === '' || !isset($store['groups'][$code])) {
        respond(false, 'Codigo nao encontrado.', null, 404);
    }

    respond(true, 'Casal carregado.', payload($store['groups'][$code], true));
}

function adminUnlockDays($input, $config, $storageDir, $storageFile)
{
    assertAdmin($input, $config, $storageDir);

    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $unlockUntilDay = cleanUnlockedDay(isset($input['unlock_until_day']) ? $input['unlock_until_day'] : 1);
    $group = null;

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $unlockUntilDay, &$group) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }

        if (!isset($store['groups'][$code]['settings']) || !is_array($store['groups'][$code]['settings'])) {
            $store['groups'][$code]['settings'] = array();
        }
        $store['groups'][$code]['settings']['manualUnlockedUntil'] = $unlockUntilDay;
        $store['groups'][$code]['lastDay'] = max(
            isset($store['groups'][$code]['lastDay']) ? (int)$store['groups'][$code]['lastDay'] : 1,
            $unlockUntilDay
        );
        $store['groups'][$code]['updatedAt'] = date('c');
        $group = $store['groups'][$code];
    });

    respond(true, 'Dias liberados para este casal.', payload($group, true));
}

function saveGuidance($input, $config, $storageDir, $storageFile)
{
    assertAdmin($input, $config, $storageDir);

    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $guidance = isset($input['guidance']) && is_array($input['guidance']) ? $input['guidance'] : array();
    $clean = cleanGuidance($guidance);
    $group = null;

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $clean, &$group) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }

        $previous = isset($store['groups'][$code]['guidance']) && is_array($store['groups'][$code]['guidance'])
            ? array_merge(defaultGuidance(), $store['groups'][$code]['guidance'])
            : defaultGuidance();
        $changed = changedLabels($previous, $clean, guidanceLabels());

        $store['groups'][$code]['guidance'] = $clean;
        if (count($changed)) {
            appendNotification($store['groups'][$code], array(
                'actor' => 'terapeuta',
                'target' => 'orientacoes',
                'title' => 'Orientacoes da terapeuta atualizadas',
                'summary' => 'Campos atualizados: ' . implode(', ', $changed) . '.',
            ));
        }
        $store['groups'][$code]['updatedAt'] = date('c');
        $group = $store['groups'][$code];
    });

    respond(true, 'Orientacoes salvas para o casal.', payload($group));
}

function ensureStorage($storageDir, $storageFile)
{
    if (!is_dir($storageDir)) {
        if (!mkdir($storageDir, 0755, true)) {
            respond(false, 'Nao foi possivel criar a pasta data no servidor.', null, 500);
        }
    }

    if (!file_exists($storageFile)) {
        $initial = json_encode(array('groups' => new stdClass()), JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
        if (file_put_contents($storageFile, $initial) === false) {
            respond(false, 'Nao foi possivel criar o arquivo de dados.', null, 500);
        }
    }
}

function ensureContentStorage($storageDir, $contentFile)
{
    if (!is_dir($storageDir)) {
        if (!mkdir($storageDir, 0755, true)) {
            respond(false, 'Nao foi possivel criar a pasta data no servidor.', null, 500);
        }
    }

    if (!file_exists($contentFile)) {
        if (file_put_contents($contentFile, json_encode(new stdClass(), JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT)) === false) {
            respond(false, 'Nao foi possivel criar o arquivo de conteudo.', null, 500);
        }
    }
}

function assertAdmin($input, $config, $storageDir)
{
    $sentPassword = isset($input['admin_password']) ? (string)$input['admin_password'] : '';
    if (strlen($sentPassword) < 4) {
        respond(false, 'Senha de administrador invalida.', null, 403);
    }

    $configPassword = isset($config['admin_password']) ? (string)$config['admin_password'] : '';
    if ($configPassword !== '') {
        if (!hash_equals($configPassword, $sentPassword)) {
            respond(false, 'Senha de administrador invalida.', null, 403);
        }
        return;
    }

    if (!is_dir($storageDir)) {
        if (!mkdir($storageDir, 0755, true)) {
            respond(false, 'Nao foi possivel criar a pasta data no servidor.', null, 500);
        }
    }

    $adminFile = $storageDir . '/admin.json';
    if (!file_exists($adminFile)) {
        $payload = array(
            'passwordHash' => password_hash($sentPassword, PASSWORD_DEFAULT),
            'createdAt' => date('c'),
        );
        if (file_put_contents($adminFile, json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), LOCK_EX) === false) {
            respond(false, 'Nao foi possivel criar a senha administrativa no servidor.', null, 500);
        }
        return;
    }

    $payload = json_decode(file_get_contents($adminFile), true);
    $hash = is_array($payload) && isset($payload['passwordHash']) ? (string)$payload['passwordHash'] : '';
    if ($hash === '' || !password_verify($sentPassword, $hash)) {
        respond(false, 'Senha de administrador invalida.', null, 403);
    }
}

function activatePendingGroups($storageDir, $storageFile)
{
    updateStore($storageDir, $storageFile, function (&$store) {
        if (!isset($store['groups']) || !is_array($store['groups'])) {
            return;
        }

        foreach ($store['groups'] as &$group) {
            if (!is_array($group) || !empty($group['activatedAt'])) {
                continue;
            }

            $now = date('c');
            $group['activatedAt'] = !empty($group['createdAt']) ? $group['createdAt'] : $now;
            $group['updatedAt'] = $now;
        }
        unset($group);
    });
}

function readStore($storageDir, $storageFile)
{
    ensureStorage($storageDir, $storageFile);
    $content = file_get_contents($storageFile);
    $store = json_decode($content, true);

    if (!is_array($store)) {
        $store = array();
    }
    if (!isset($store['groups']) || !is_array($store['groups'])) {
        $store['groups'] = array();
    }

    return $store;
}

function updateStore($storageDir, $storageFile, $callback)
{
    ensureStorage($storageDir, $storageFile);

    $handle = fopen($storageFile, 'c+');
    if (!$handle) {
        respond(false, 'Nao foi possivel abrir o arquivo de dados.', null, 500);
    }

    if (!flock($handle, LOCK_EX)) {
        fclose($handle);
        respond(false, 'Nao foi possivel bloquear o arquivo de dados.', null, 500);
    }

    $content = stream_get_contents($handle);
    $store = json_decode($content, true);
    if (!is_array($store)) {
        $store = array();
    }
    if (!isset($store['groups']) || !is_array($store['groups'])) {
        $store['groups'] = array();
    }

    $callback($store);

    rewind($handle);
    ftruncate($handle, 0);
    fwrite($handle, json_encode($store, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    fflush($handle);
    flock($handle, LOCK_UN);
    fclose($handle);
}

function readContent($storageDir, $contentFile)
{
    ensureContentStorage($storageDir, $contentFile);
    $content = json_decode(file_get_contents($contentFile), true);
    return is_array($content) ? $content : array();
}

function updateContent($storageDir, $contentFile, $callback)
{
    ensureContentStorage($storageDir, $contentFile);

    $handle = fopen($contentFile, 'c+');
    if (!$handle) {
        respond(false, 'Nao foi possivel abrir o arquivo de conteudo.', null, 500);
    }

    if (!flock($handle, LOCK_EX)) {
        fclose($handle);
        respond(false, 'Nao foi possivel bloquear o arquivo de conteudo.', null, 500);
    }

    $contentStore = json_decode(stream_get_contents($handle), true);
    if (!is_array($contentStore)) {
        $contentStore = array();
    }

    $callback($contentStore);

    rewind($handle);
    ftruncate($handle, 0);
    fwrite($handle, json_encode($contentStore, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    fflush($handle);
    flock($handle, LOCK_UN);
    fclose($handle);
}

function generateCode($store)
{
    do {
        $code = 'LAR-' . random_int(100000, 999999);
    } while (isset($store['groups'][$code]));

    return $code;
}

function normalizeCode($code)
{
    $raw = strtoupper(trim((string)$code));
    if (preg_match('/LAR-?([0-9]{6})/', $raw, $matches)) {
        return 'LAR-' . $matches[1];
    }
    return strtoupper(preg_replace('/\s+/', '', $raw));
}

function cleanText($text)
{
    return trim(strip_tags((string)$text));
}

function cleanParagraphs($paragraphs)
{
    if (!is_array($paragraphs)) {
        $paragraphs = array((string)$paragraphs);
    }

    $clean = array();
    foreach ($paragraphs as $paragraph) {
        $text = cleanText($paragraph);
        if ($text !== '') {
            $clean[] = $text;
        }
    }
    return $clean;
}

function defaultGuidance()
{
    return array(
        'couple' => '',
        'partnerOne' => '',
        'partnerTwo' => '',
        'doList' => '',
        'avoidList' => '',
        'exercise' => '',
        'message' => '',
        'customTopics' => array(),
    );
}

function defaultJourneyShared()
{
    return array(
        'dreams' => '',
        'building' => '',
        'improveSelf' => '',
        'improveOther' => '',
        'difficultTalk' => '',
        'recognizeGood' => '',
        'prayerRequest' => '',
        'dreamsShort' => array(),
        'dreamsMedium' => array(),
        'dreamsLong' => array(),
        'improvementsOne' => array(),
        'improvementsTwo' => array(),
        'improveOne' => '',
        'improveTwo' => '',
        'recognizeOne' => '',
        'recognizeTwo' => '',
        'customTopics' => array(),
    );
}

function cleanGuidance($guidance)
{
    $default = defaultGuidance();
    foreach ($default as $key => $value) {
        if ($key === 'customTopics') {
            $default[$key] = cleanCustomTopics(isset($guidance[$key]) ? $guidance[$key] : array());
        } else {
            $default[$key] = cleanText(isset($guidance[$key]) ? $guidance[$key] : '');
        }
    }
    return $default;
}

function cleanJourneyShared($journey)
{
    $default = defaultJourneyShared();
    foreach ($default as $key => $value) {
        if ($key === 'customTopics') {
            $default[$key] = cleanCustomTopics(isset($journey[$key]) ? $journey[$key] : array());
        } elseif (is_array($value)) {
            $default[$key] = cleanChecklistItems(isset($journey[$key]) ? $journey[$key] : array());
        } else {
            $default[$key] = cleanText(isset($journey[$key]) ? $journey[$key] : '');
        }
    }
    return $default;
}

function cleanChecklistItems($items)
{
    if (!is_array($items)) {
        return array();
    }

    $clean = array();
    foreach ($items as $item) {
        if (is_array($item)) {
            $text = cleanText(isset($item['text']) ? $item['text'] : '');
            $done = !empty($item['done']);
        } else {
            $text = cleanText($item);
            $done = false;
        }

        if ($text !== '') {
            $clean[] = array(
                'text' => $text,
                'done' => $done,
            );
        }
    }

    return array_slice($clean, 0, 80);
}

function cleanCustomTopics($items)
{
    if (!is_array($items)) {
        return array();
    }

    $clean = array();
    foreach ($items as $item) {
        if (!is_array($item)) {
            continue;
        }

        $title = cleanText(isset($item['title']) ? $item['title'] : '');
        $text = cleanText(isset($item['text']) ? $item['text'] : '');

        if ($title !== '' || $text !== '') {
            $clean[] = array(
                'title' => $title !== '' ? $title : 'Topico personalizado',
                'text' => $text,
            );
        }
    }

    return array_slice($clean, 0, 30);
}

function guidanceLabels()
{
    return array(
        'couple' => 'orientacao para o casal',
        'partnerOne' => 'orientacao para pessoa 1',
        'partnerTwo' => 'orientacao para pessoa 2',
        'doList' => 'o que fazer',
        'avoidList' => 'o que evitar',
        'exercise' => 'exercicio da semana',
        'message' => 'mensagem da terapeuta',
        'customTopics' => 'outros topicos da terapeuta',
    );
}

function journeyLabels()
{
    return array(
        'dreamsShort' => 'sonhos de curto prazo',
        'dreamsMedium' => 'sonhos de medio prazo',
        'dreamsLong' => 'sonhos de longo prazo',
        'improveOne' => 'pontos a melhorar pessoa 1',
        'improveTwo' => 'pontos a melhorar pessoa 2',
        'recognizeOne' => 'reconhecimentos pessoa 1',
        'recognizeTwo' => 'reconhecimentos pessoa 2',
        'customTopics' => 'topicos personalizados',
        'dreams' => 'nossos sonhos antigos',
        'building' => 'o que esperamos construir',
        'improveSelf' => 'pontos que precisamos melhorar',
        'improveOther' => 'pontos que esperamos do outro',
        'difficultTalk' => 'dificuldades para falar',
        'recognizeGood' => 'o que reconhecemos de bom',
        'prayerRequest' => 'pedido de oracao',
    );
}

function changedLabels($previous, $next, $labels)
{
    $changed = array();
    foreach ($labels as $key => $label) {
        $oldValue = normalizeChangeValue(isset($previous[$key]) ? $previous[$key] : '');
        $newValue = normalizeChangeValue(isset($next[$key]) ? $next[$key] : '');
        if ($oldValue !== $newValue) {
            $changed[] = $label;
        }
    }
    return $changed;
}

function normalizeChangeValue($value)
{
    if (is_array($value)) {
        return json_encode($value, JSON_UNESCAPED_UNICODE);
    }
    return trim((string)$value);
}

function appendNotification(&$group, $notification)
{
    if (!isset($group['notifications']) || !is_array($group['notifications'])) {
        $group['notifications'] = array();
    }

    array_unshift($group['notifications'], array(
        'id' => uniqid('upd_', true),
        'actor' => isset($notification['actor']) ? $notification['actor'] : 'sistema',
        'target' => isset($notification['target']) ? $notification['target'] : 'geral',
        'title' => isset($notification['title']) ? $notification['title'] : 'Atualizacao registrada',
        'summary' => isset($notification['summary']) ? $notification['summary'] : '',
        'createdAt' => date('c'),
    ));

    $group['notifications'] = array_slice($group['notifications'], 0, 30);
}

function cleanDate($date)
{
    $parsed = DateTime::createFromFormat('Y-m-d', (string)$date);
    return $parsed ? $parsed->format('Y-m-d') : date('Y-m-d');
}

function cleanDay($day)
{
    $day = (int)$day;
    if ($day < 1 || $day > 21) {
        respond(false, 'Dia invalido.', null, 422);
    }
    return $day;
}

function cleanUnlockedDay($day)
{
    $day = (int)$day;
    if ($day < 1) {
        return 1;
    }
    if ($day > 21) {
        return 21;
    }
    return $day;
}

function savePrivateNote($input, $storageDir, $storageFile)
{
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $memberId = isset($input['member_id']) ? (int)$input['member_id'] : 0;
    $password = isset($input['password']) ? (string)$input['password'] : '';
    $note = isset($input['note']) ? substr(cleanText($input['note']), 0, 5000) : '';
    $group = null;

    if ($memberId !== 1 && $memberId !== 2) {
        respond(false, 'Participante invalido.', null, 422);
    }
    if (strlen($password) < 4) {
        respond(false, 'Informe a senha privada.', null, 422);
    }

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $memberId, $password, $note, &$group) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }
        if (!verifyPrivatePassword($store['groups'][$code], $memberId, $password)) {
            respond(false, 'Senha privada incorreta.', null, 403);
        }
        if (!isset($store['groups'][$code]['privateNotes']) || !is_array($store['groups'][$code]['privateNotes'])) {
            $store['groups'][$code]['privateNotes'] = array();
        }
        $store['groups'][$code]['privateNotes'][$memberId] = $note;
        $store['groups'][$code]['updatedAt'] = date('c');
        appendNotification($store['groups'][$code], array(
            'actor' => 'casal',
            'target' => 'privado',
            'title' => $note === '' ? 'Mensagem privada apagada' : 'Nova mensagem privada',
            'summary' => $note === '' ? 'Mensagem removida pelo participante.' : 'Mensagem enviada para a terapeuta.',
        ));
        $group = $store['groups'][$code];
    });

    respond(true, 'Mensagem privada salva.', array(
        'note' => $note,
        'replies' => privateRepliesForMember($group, $memberId),
        'chat' => privateChatForMember($group, $memberId),
    ));
}

function sendPrivateMessage($input, $storageDir, $storageFile)
{
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $memberId = isset($input['member_id']) ? (int)$input['member_id'] : 0;
    $password = isset($input['password']) ? (string)$input['password'] : '';
    $text = isset($input['text']) ? substr(cleanText($input['text']), 0, 3000) : '';
    $group = null;

    if ($memberId !== 1 && $memberId !== 2) {
        respond(false, 'Participante invalido.', null, 422);
    }
    if (strlen($password) < 4) {
        respond(false, 'Informe a senha privada.', null, 422);
    }
    if ($text === '') {
        respond(false, 'Escreva uma mensagem antes de enviar.', null, 422);
    }

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $memberId, $password, $text, &$group) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }
        if (!verifyPrivatePassword($store['groups'][$code], $memberId, $password)) {
            respond(false, 'Senha privada incorreta.', null, 403);
        }

        ensurePrivateChat($store['groups'][$code], $memberId);
        $store['groups'][$code]['privateChats'][$memberId][] = array(
            'id' => uniqid('msg_', true),
            'author' => 'participante',
            'text' => $text,
            'createdAt' => date('c'),
        );
        $store['groups'][$code]['updatedAt'] = date('c');
        appendNotification($store['groups'][$code], array(
            'actor' => 'casal',
            'target' => 'privado',
            'title' => 'Nova mensagem privada',
            'summary' => 'Mensagem enviada para a terapeuta.',
        ));
        $group = $store['groups'][$code];
    });

    respond(true, 'Mensagem enviada.', array(
        'chat' => privateChatForMember($group, $memberId),
    ));
}

function deletePrivateMessage($input, $storageDir, $storageFile)
{
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $memberId = isset($input['member_id']) ? (int)$input['member_id'] : 0;
    $password = isset($input['password']) ? (string)$input['password'] : '';
    $messageId = isset($input['message_id']) ? (string)$input['message_id'] : '';
    $group = null;

    if ($memberId !== 1 && $memberId !== 2) {
        respond(false, 'Participante invalido.', null, 422);
    }
    if ($messageId === '') {
        respond(false, 'Mensagem invalida.', null, 422);
    }

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $memberId, $password, $messageId, &$group) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }
        if (!verifyPrivatePassword($store['groups'][$code], $memberId, $password)) {
            respond(false, 'Senha privada incorreta.', null, 403);
        }

        ensurePrivateChat($store['groups'][$code], $memberId);
        $chat = isset($store['groups'][$code]['privateChats'][$memberId])
            ? $store['groups'][$code]['privateChats'][$memberId]
            : array();
        $store['groups'][$code]['privateChats'][$memberId] = array_values(array_filter($chat, function ($message) use ($messageId) {
            return !is_array($message)
                || !isset($message['id'])
                || $message['id'] !== $messageId
                || (isset($message['author']) && $message['author'] !== 'participante');
        }));
        if ($messageId === 'legacy_note_' . $memberId
            && isset($store['groups'][$code]['privateNotes'])
            && is_array($store['groups'][$code]['privateNotes'])) {
            $store['groups'][$code]['privateNotes'][$memberId] = '';
        }
        $store['groups'][$code]['updatedAt'] = date('c');
        appendNotification($store['groups'][$code], array(
            'actor' => 'casal',
            'target' => 'privado',
            'title' => 'Mensagem privada apagada',
            'summary' => 'Uma mensagem do chat privado foi removida.',
        ));
        $group = $store['groups'][$code];
    });

    respond(true, 'Mensagem apagada.', array(
        'chat' => privateChatForMember($group, $memberId),
    ));
}

function adminDeletePrivateMessage($input, $config, $storageDir, $storageFile)
{
    assertAdmin($input, $config, $storageDir);

    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $memberId = isset($input['member_id']) ? (int)$input['member_id'] : 0;
    $messageId = isset($input['message_id']) ? (string)$input['message_id'] : '';
    $group = null;

    if ($memberId !== 1 && $memberId !== 2) {
        respond(false, 'Participante invalido.', null, 422);
    }
    if ($messageId === '') {
        respond(false, 'Mensagem invalida.', null, 422);
    }

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $memberId, $messageId, &$group) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }

        ensurePrivateChat($store['groups'][$code], $memberId);
        $chat = isset($store['groups'][$code]['privateChats'][$memberId])
            ? $store['groups'][$code]['privateChats'][$memberId]
            : array();
        $canDelete = false;
        foreach ($chat as $message) {
            if (is_array($message)
                && isset($message['id'])
                && $message['id'] === $messageId
                && isset($message['author'])
                && $message['author'] === 'terapeuta') {
                $canDelete = true;
                break;
            }
        }
        if (!$canDelete) {
            respond(false, 'No admin, a terapeuta so pode apagar mensagens dela.', null, 403);
        }
        $store['groups'][$code]['privateChats'][$memberId] = array_values(array_filter($chat, function ($message) use ($messageId) {
            return !is_array($message) || !isset($message['id']) || $message['id'] !== $messageId;
        }));

        if (isset($store['groups'][$code]['privateReplies'])
            && is_array($store['groups'][$code]['privateReplies'])
            && isset($store['groups'][$code]['privateReplies'][$memberId])
            && is_array($store['groups'][$code]['privateReplies'][$memberId])) {
            $store['groups'][$code]['privateReplies'][$memberId] = array_values(array_filter(
                $store['groups'][$code]['privateReplies'][$memberId],
                function ($reply) use ($messageId) {
                    return !is_array($reply) || !isset($reply['id']) || $reply['id'] !== $messageId;
                }
            ));
        }
        if (isset($store['groups'][$code]['privateReplies'])
            && is_array($store['groups'][$code]['privateReplies'])
            && isset($store['groups'][$code]['privateReplies'][(string)$memberId])
            && is_array($store['groups'][$code]['privateReplies'][(string)$memberId])) {
            $store['groups'][$code]['privateReplies'][(string)$memberId] = array_values(array_filter(
                $store['groups'][$code]['privateReplies'][(string)$memberId],
                function ($reply) use ($messageId) {
                    return !is_array($reply) || !isset($reply['id']) || $reply['id'] !== $messageId;
                }
            ));
        }

        $store['groups'][$code]['updatedAt'] = date('c');
        appendNotification($store['groups'][$code], array(
            'actor' => 'terapeuta',
            'target' => 'privado',
            'title' => 'Mensagem privada apagada',
            'summary' => 'Uma mensagem do chat privado foi removida pela terapeuta.',
        ));
        $group = $store['groups'][$code];
    });

    respond(true, 'Mensagem apagada.', payload($group, true));
}

function markPrivateChatRead($input, $config, $storageDir, $storageFile)
{
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $memberId = isset($input['member_id']) ? (int)$input['member_id'] : 0;
    $reader = isset($input['reader']) ? (string)$input['reader'] : '';
    $group = null;

    if ($memberId !== 1 && $memberId !== 2) {
        respond(false, 'Participante invalido.', null, 422);
    }

    if ($reader === 'therapist') {
        assertAdmin($input, $config, $storageDir);
    } elseif ($reader === 'participant') {
        $password = isset($input['password']) ? (string)$input['password'] : '';
    } else {
        respond(false, 'Leitor invalido.', null, 422);
    }

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $memberId, $reader, &$group, $input) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }
        if ($reader === 'participant') {
            $password = isset($input['password']) ? (string)$input['password'] : '';
            if (!verifyPrivatePassword($store['groups'][$code], $memberId, $password)) {
                respond(false, 'Senha privada incorreta.', null, 403);
            }
        }

        markPrivateRead($store['groups'][$code], $reader, $memberId);
        $store['groups'][$code]['updatedAt'] = date('c');
        $group = $store['groups'][$code];
    });

    respond(true, 'Chat marcado como lido.', payload($group, true));
}

function privateNoteStatus($input, $storageDir, $storageFile)
{
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $memberId = isset($input['member_id']) ? (int)$input['member_id'] : 0;

    if ($memberId !== 1 && $memberId !== 2) {
        respond(false, 'Participante invalido.', null, 422);
    }

    $store = readStore($storageDir, $storageFile);

    if (!isset($store['groups'][$code])) {
        respond(false, 'Codigo nao encontrado.', null, 404);
    }

    respond(true, 'Status carregado.', array(
        'hasPassword' => hasPrivatePassword($store['groups'][$code], $memberId),
        'hasUnread' => privateUnreadState($store['groups'][$code])['participant'][$memberId],
    ));
}

function unlockPrivateNote($input, $storageDir, $storageFile)
{
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $memberId = isset($input['member_id']) ? (int)$input['member_id'] : 0;
    $password = isset($input['password']) ? (string)$input['password'] : '';
    $note = '';
    $replies = array();
    $chat = array();

    if ($memberId !== 1 && $memberId !== 2) {
        respond(false, 'Participante invalido.', null, 422);
    }
    if (strlen($password) < 4) {
        respond(false, 'A senha precisa ter pelo menos 4 caracteres.', null, 422);
    }

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $memberId, $password, &$note, &$replies, &$chat) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }

        if (!hasPrivatePassword($store['groups'][$code], $memberId)) {
            if (!isset($store['groups'][$code]['privateNotePasswords']) || !is_array($store['groups'][$code]['privateNotePasswords'])) {
                $store['groups'][$code]['privateNotePasswords'] = array();
            }
            $store['groups'][$code]['privateNotePasswords'][$memberId] = password_hash($password, PASSWORD_DEFAULT);
            $store['groups'][$code]['updatedAt'] = date('c');
        } elseif (!verifyPrivatePassword($store['groups'][$code], $memberId, $password)) {
            respond(false, 'Senha privada incorreta.', null, 403);
        }

        $privateNotes = isset($store['groups'][$code]['privateNotes']) && is_array($store['groups'][$code]['privateNotes'])
            ? $store['groups'][$code]['privateNotes']
            : array();
        $note = isset($privateNotes[$memberId]) ? $privateNotes[$memberId] : '';
        $replies = privateRepliesForMember($store['groups'][$code], $memberId);
        ensurePrivateChat($store['groups'][$code], $memberId);
        $chat = privateChatForMember($store['groups'][$code], $memberId);
        markPrivateRead($store['groups'][$code], 'participant', $memberId);
    });

    respond(true, 'Mensagem liberada.', array('note' => $note, 'replies' => $replies, 'chat' => $chat));
}

function getPrivateNote($input, $storageDir, $storageFile)
{
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $memberId = isset($input['member_id']) ? (int)$input['member_id'] : 0;
    $password = isset($input['password']) ? (string)$input['password'] : '';
    $note = '';
    $replies = array();
    $chat = array();

    if ($memberId !== 1 && $memberId !== 2) {
        respond(false, 'Participante invalido.', null, 422);
    }

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $memberId, $password, &$note, &$replies, &$chat) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }
        if (!verifyPrivatePassword($store['groups'][$code], $memberId, $password)) {
            respond(false, 'Senha privada incorreta.', null, 403);
        }

        $privateNotes = isset($store['groups'][$code]['privateNotes']) ? $store['groups'][$code]['privateNotes'] : array();
        $note = isset($privateNotes[$memberId]) ? $privateNotes[$memberId] : '';
        $replies = privateRepliesForMember($store['groups'][$code], $memberId);
        ensurePrivateChat($store['groups'][$code], $memberId);
        $chat = privateChatForMember($store['groups'][$code], $memberId);
        markPrivateRead($store['groups'][$code], 'participant', $memberId);
    });

    respond(true, 'Mensagem carregada.', array('note' => $note, 'replies' => $replies, 'chat' => $chat));
}

function savePrivateReply($input, $config, $storageDir, $storageFile)
{
    assertAdmin($input, $config, $storageDir);

    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $memberId = isset($input['member_id']) ? (int)$input['member_id'] : 0;
    $text = isset($input['text']) ? substr(cleanText($input['text']), 0, 3000) : '';
    $group = null;

    if ($memberId !== 1 && $memberId !== 2) {
        respond(false, 'Participante invalido.', null, 422);
    }
    if ($text === '') {
        respond(false, 'Escreva a resposta da terapeuta.', null, 422);
    }

    updateStore($storageDir, $storageFile, function (&$store) use ($code, $memberId, $text, &$group) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }

        if (!isset($store['groups'][$code]['privateReplies']) || !is_array($store['groups'][$code]['privateReplies'])) {
            $store['groups'][$code]['privateReplies'] = array();
        }
        if (!isset($store['groups'][$code]['privateReplies'][$memberId]) || !is_array($store['groups'][$code]['privateReplies'][$memberId])) {
            $store['groups'][$code]['privateReplies'][$memberId] = array();
        }

        ensurePrivateChat($store['groups'][$code], $memberId);

        $reply = array(
            'id' => uniqid('reply_', true),
            'author' => 'terapeuta',
            'text' => $text,
            'createdAt' => date('c'),
        );

        array_unshift($store['groups'][$code]['privateReplies'][$memberId], $reply);
        $store['groups'][$code]['privateChats'][$memberId][] = $reply;

        $store['groups'][$code]['privateReplies'][$memberId] = array_slice($store['groups'][$code]['privateReplies'][$memberId], 0, 50);
        $store['groups'][$code]['updatedAt'] = date('c');
        appendNotification($store['groups'][$code], array(
            'actor' => 'terapeuta',
            'target' => 'privado',
            'title' => 'Nova resposta privada da terapeuta',
            'summary' => 'Mensagem privada respondida.',
        ));
        $group = $store['groups'][$code];
    });

    respond(true, 'Resposta enviada.', payload($group, true));
}

function privateRepliesForMember($group, $memberId)
{
    $privateReplies = isset($group['privateReplies']) && is_array($group['privateReplies'])
        ? $group['privateReplies']
        : array();

    return isset($privateReplies[$memberId]) && is_array($privateReplies[$memberId])
        ? $privateReplies[$memberId]
        : array();
}

function ensurePrivateChat(&$group, $memberId)
{
    if (!isset($group['privateChats']) || !is_array($group['privateChats'])) {
        $group['privateChats'] = array();
    }
    if (isset($group['privateChats'][$memberId]) && is_array($group['privateChats'][$memberId])) {
        return;
    }

    $chat = array();
    $privateNotes = isset($group['privateNotes']) && is_array($group['privateNotes']) ? $group['privateNotes'] : array();
    $note = isset($privateNotes[$memberId]) ? trim((string)$privateNotes[$memberId]) : '';

    if ($note !== '') {
        $chat[] = array(
            'id' => 'legacy_note_' . $memberId,
            'author' => 'participante',
            'text' => $note,
            'createdAt' => isset($group['updatedAt']) ? $group['updatedAt'] : date('c'),
        );
    }

    $replies = privateRepliesForMember($group, $memberId);
    $replies = array_reverse($replies);
    foreach ($replies as $reply) {
        if (!is_array($reply)) {
            continue;
        }
        $text = isset($reply['text']) ? trim((string)$reply['text']) : '';
        if ($text === '') {
            continue;
        }
        $chat[] = array(
            'id' => isset($reply['id']) ? (string)$reply['id'] : uniqid('legacy_reply_', true),
            'author' => 'terapeuta',
            'text' => $text,
            'createdAt' => isset($reply['createdAt']) ? (string)$reply['createdAt'] : date('c'),
        );
    }

    usort($chat, function ($a, $b) {
        return strcmp(isset($a['createdAt']) ? $a['createdAt'] : '', isset($b['createdAt']) ? $b['createdAt'] : '');
    });

    $group['privateChats'][$memberId] = $chat;
}

function privateChatForMember($group, $memberId)
{
    $chat = isset($group['privateChats'])
        && is_array($group['privateChats'])
        && isset($group['privateChats'][$memberId])
        && is_array($group['privateChats'][$memberId])
        ? $group['privateChats'][$memberId]
        : array();

    $clean = array();
    $seen = array();
    foreach ($chat as $message) {
        if (!is_array($message)) {
            continue;
        }
        $text = isset($message['text']) ? trim((string)$message['text']) : '';
        if ($text === '') {
            continue;
        }
        $author = isset($message['author']) && $message['author'] === 'terapeuta' ? 'terapeuta' : 'participante';
        $id = isset($message['id']) ? (string)$message['id'] : '';
        $createdAt = isset($message['createdAt']) ? (string)$message['createdAt'] : '';
        $dedupeKey = $id !== '' ? $id : md5($author . '|' . $createdAt . '|' . $text);
        if (isset($seen[$dedupeKey])) {
            continue;
        }
        $seen[$dedupeKey] = true;
        $clean[] = array(
            'id' => $id !== '' ? $id : uniqid('msg_', true),
            'author' => $author,
            'text' => $text,
            'createdAt' => $createdAt,
        );
    }

    usort($clean, function ($a, $b) {
        return strcmp(isset($a['createdAt']) ? $a['createdAt'] : '', isset($b['createdAt']) ? $b['createdAt'] : '');
    });

    return $clean;
}

function markPrivateRead(&$group, $reader, $memberId)
{
    if (!isset($group['privateReadAt']) || !is_array($group['privateReadAt'])) {
        $group['privateReadAt'] = array();
    }
    if (!isset($group['privateReadAt'][$reader]) || !is_array($group['privateReadAt'][$reader])) {
        $group['privateReadAt'][$reader] = array();
    }
    $group['privateReadAt'][$reader][$memberId] = date('c');
}

function privateUnreadState($group)
{
    $state = array(
        'therapist' => array(1 => false, 2 => false),
        'participant' => array(1 => false, 2 => false),
    );

    for ($memberId = 1; $memberId <= 2; $memberId++) {
        ensurePrivateChat($group, $memberId);
        $chat = privateChatForMember($group, $memberId);
        $state['therapist'][$memberId] = hasUnreadPrivateMessages($group, $chat, 'therapist', 'participante', $memberId);
        $state['participant'][$memberId] = hasUnreadPrivateMessages($group, $chat, 'participant', 'terapeuta', $memberId);
    }

    return $state;
}

function hasUnreadPrivateMessages($group, $chat, $reader, $author, $memberId)
{
    $readAt = '';
    if (isset($group['privateReadAt'])
        && is_array($group['privateReadAt'])
        && isset($group['privateReadAt'][$reader])
        && is_array($group['privateReadAt'][$reader])
        && !empty($group['privateReadAt'][$reader][$memberId])) {
        $readAt = (string)$group['privateReadAt'][$reader][$memberId];
    }

    foreach ($chat as $message) {
        if (!is_array($message)) {
            continue;
        }
        $messageAuthor = isset($message['author']) ? (string)$message['author'] : '';
        $createdAt = isset($message['createdAt']) ? (string)$message['createdAt'] : '';
        if ($messageAuthor === $author && $createdAt !== '' && ($readAt === '' || strcmp($createdAt, $readAt) > 0)) {
            return true;
        }
    }

    return false;
}

function hasPrivatePassword($group, $memberId)
{
    return isset($group['privateNotePasswords'])
        && is_array($group['privateNotePasswords'])
        && !empty($group['privateNotePasswords'][$memberId]);
}

function verifyPrivatePassword($group, $memberId, $password)
{
    if (!hasPrivatePassword($group, $memberId)) {
        return false;
    }
    return password_verify((string)$password, (string)$group['privateNotePasswords'][$memberId]);
}

function adminResetPrivatePassword($input, $config, $storageDir, $storageFile)
{
    assertAdmin($input, $config, $storageDir);
    $code = normalizeCode(isset($input['access_code']) ? $input['access_code'] : '');
    $memberId = isset($input['member_id']) ? (int)$input['member_id'] : 0;
    if ($memberId !== 1 && $memberId !== 2) {
        respond(false, 'Participante invalido.', null, 422);
    }
    $group = null;
    updateStore($storageDir, $storageFile, function (&$store) use ($code, $memberId, &$group) {
        if (!isset($store['groups'][$code])) {
            respond(false, 'Codigo nao encontrado.', null, 404);
        }
        if (isset($store['groups'][$code]['privateNotePasswords']) && is_array($store['groups'][$code]['privateNotePasswords'])) {
            unset($store['groups'][$code]['privateNotePasswords'][$memberId]);
        }
        $store['groups'][$code]['updatedAt'] = date('c');
        appendNotification($store['groups'][$code], array(
            'actor' => 'terapeuta',
            'target' => 'privado',
            'title' => 'Senha privada resetada',
            'summary' => 'A terapeuta resetou a senha do chat privado do participante ' . $memberId . '.',
        ));
        $group = $store['groups'][$code];
    });
    respond(true, 'Senha privada resetada com sucesso.', payload($group, true));
}

function respond($ok, $message, $data = null, $status = 200)
{
    http_response_code($status);
    echo json_encode(array(
        'ok' => $ok,
        'message' => $message,
        'data' => $data,
    ), JSON_UNESCAPED_UNICODE);
    exit;
}
