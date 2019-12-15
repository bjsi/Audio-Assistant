from models import ItemFile, TopicFile, ExtractFile, session


def remove_finished_topics():
    """ Remove finished topics
    Finished means it satisfies all of the following:
    - Over 90% completed
    - topic.archived is True
    - No outstanding extracts
    """
    # Find topics to be deleted
    topics = (session
              .query(TopicFile)
              .filter_by(deleted=False)
              .filter_by(archived=True)
              # Shouldn't be necessary because of check_progress
              # sqlalchemy function
              .filter((TopicFile.cur_timestamp/TopicFile.duration) < 0.9)
              .all())

    if topics:
        for topic in topics:
            extracts = topic.extracts
            if all(
                    extract.archived
                    for extract in extracts
                  ):
                # TODO Delete the topic
                # Check for existence
                # Delete verbosely
                # if successfully deleted
                topic.deleted = True
                session.commit()
    else:
        print("No Topics to delete!")


def remove_finished_extracts():
    """ Remove finished extracts
    Finish means it satisfies the following:
    - extract.archived is True
    - No outstanding child items
    """
    # Find extracts to be deleted
    extracts = (session
                .query(ExtractFile)
                .filter_by(deleted=False)
                .filter_by(archived=True)
                .all())

    if extracts:
        for extract in extracts:
            # Check that all child items are archived
            items = extract.items
            if all(
                    item.archived
                    for item in items
                  ):
                # TODO Delete the extract
                # Check for existence
                # Delete verbosely
                # if successfully deleted
                extract.deleted = True
                session.commit()
    else:
        print("No extracts to delete!")


def remove_finished_items():
    """ Remove finished items
    Finished means it satisfies the following:
    - item.archived is True
    """

    # Find items to be deleted
    items = (session
             .query(ItemFile)
             .filter_by(deleted=False)
             .filter_by(archived=True)
             .all())

    if items:
        for item in items:
            if item.archived:
                # TODO Delete the item
                # Check for existence
                # Delete verbosely
                # if successfully deleted
                item.deleted = True
                session.commit()
    else:
        print("No Items to delete!")


if __name__ == "__main__":
    """ Delete all finished files
    Start with items, then extracts, then topics"""
    remove_finished_items()
    remove_finished_extracts()
    remove_finished_topics()
